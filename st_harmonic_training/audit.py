from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from .contracts import (
    AcquisitionStatus,
    AdjudicationOutcome,
    GoldTier,
    SourceManifest,
    TEACHER_GOLD_TIERS,
)
from .identity import WorkIdentity
from .normalization import NORMALIZATION_VERSION
from .split import Partition, SplitRecord, leakage_violations


@dataclass(frozen=True)
class AuditSample:
    identity: WorkIdentity
    partition: Partition
    gold_tier: GoldTier
    adjudication_outcome: AdjudicationOutcome
    class_label: str | None
    annotation_provenance: str | None
    normalization_version: str | None
    file_status: str = "OK"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuditSample":
        identity = WorkIdentity(
            record_id=str(data["record_id"]),
            source_corpus=str(data["source_corpus"]),
            source_record_id=str(data["source_record_id"]),
            canonical_work_id=str(data["canonical_work_id"]),
            edition_id=str(data["edition_id"]),
            duplicate_cluster_id=str(data["duplicate_cluster_id"]),
            derivation_parent_id=data.get("derivation_parent_id"),
            split_group_id=str(data["split_group_id"]),
        )
        class_label = data.get("class_label")
        annotation = data.get("annotation_provenance")
        normalization = data.get("normalization_version")
        file_status = data.get("file_status", "OK")
        for name, value in (
            ("class_label", class_label),
            ("annotation_provenance", annotation),
            ("normalization_version", normalization),
        ):
            if value is not None and not isinstance(value, str):
                raise ValueError(f"{name} must be string or null")
        if not isinstance(file_status, str):
            raise ValueError("file_status must be string")
        return cls(
            identity=identity,
            partition=Partition(str(data["partition"])),
            gold_tier=GoldTier(str(data["gold_tier"])),
            adjudication_outcome=AdjudicationOutcome(str(data["adjudication_outcome"])),
            class_label=class_label,
            annotation_provenance=annotation,
            normalization_version=normalization,
            file_status=file_status,
        )


@dataclass(frozen=True)
class DatasetAuditReport:
    corpus_work_counts: dict[str, int]
    gold_tier_distribution: dict[str, int]
    split_distribution: dict[str, int]
    duplicate_clusters: dict[str, int]
    leakage_violations: tuple[str, ...]
    unresolved_licenses: tuple[str, ...]
    missing_hashes: dict[str, tuple[str, ...]]
    annotation_provenance_missing: int
    corrupt_or_unsupported: tuple[str, ...]
    class_distribution: dict[str, int]
    ambiguous_gold_count: int
    quarantined_sample_count: int
    candidate_sources_missing_manifests: tuple[str, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    training_authorized: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "corpus_work_counts": self.corpus_work_counts,
            "gold_tier_distribution": self.gold_tier_distribution,
            "split_distribution": self.split_distribution,
            "duplicate_clusters": self.duplicate_clusters,
            "leakage_violations": list(self.leakage_violations),
            "unresolved_licenses": list(self.unresolved_licenses),
            "missing_hashes": {key: list(value) for key, value in self.missing_hashes.items()},
            "annotation_provenance_missing": self.annotation_provenance_missing,
            "corrupt_or_unsupported": list(self.corrupt_or_unsupported),
            "class_distribution": self.class_distribution,
            "ambiguous_gold_count": self.ambiguous_gold_count,
            "quarantined_sample_count": self.quarantined_sample_count,
            "candidate_sources_missing_manifests": list(self.candidate_sources_missing_manifests),
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "gate_status": "PASS" if self.training_authorized else "HOLD",
            "training_authorized": self.training_authorized,
        }


def _sorted_counter(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def audit_dataset(
    *,
    candidate_sources: list[str],
    source_manifests: list[SourceManifest],
    samples: list[AuditSample],
) -> DatasetAuditReport:
    blockers: set[str] = set()
    warnings: set[str] = set()

    manifest_by_corpus = {manifest.source_corpus: manifest for manifest in source_manifests}
    missing_manifests = tuple(sorted(set(candidate_sources) - set(manifest_by_corpus)))
    for corpus in missing_manifests:
        blockers.add(f"SOURCE_MANIFEST_MISSING:{corpus}")

    ready_sources = [m for m in source_manifests if m.acquisition_status is AcquisitionStatus.READY]
    if not ready_sources:
        blockers.add("NO_READY_SOURCE")

    unresolved_licenses = tuple(sorted(
        m.source_corpus
        for m in source_manifests
        if m.license_id.strip().upper() in {"UNKNOWN", "UNRESOLVED", "NONE"}
    ))
    missing_hashes: dict[str, tuple[str, ...]] = {}
    for manifest in sorted(source_manifests, key=lambda item: item.source_corpus):
        missing = tuple(
            name
            for name, value in (
                ("raw_archive_sha256", manifest.raw_archive_sha256),
                ("score_sha256", manifest.score_sha256),
                ("analysis_sha256", manifest.analysis_sha256),
            )
            if value is None
        )
        if missing:
            missing_hashes[manifest.source_corpus] = missing

    works_by_corpus: dict[str, set[str]] = defaultdict(set)
    gold_counter: Counter[str] = Counter()
    split_counter: Counter[str] = Counter()
    duplicate_counter: Counter[str] = Counter()
    class_counter: Counter[str] = Counter()
    annotation_missing = 0
    file_issues: list[str] = []
    ambiguous_count = 0
    quarantined_count = 0

    for sample in samples:
        works_by_corpus[sample.identity.source_corpus].add(sample.identity.canonical_work_id)
        gold_counter[sample.gold_tier.value] += 1
        split_counter[sample.partition.value] += 1
        duplicate_counter[sample.identity.duplicate_cluster_id] += 1
        if sample.class_label:
            class_counter[sample.class_label] += 1
        if sample.adjudication_outcome is AdjudicationOutcome.AMBIGUOUS:
            ambiguous_count += 1
        if sample.partition is Partition.QUARANTINE or sample.gold_tier is GoldTier.QUARANTINE:
            quarantined_count += 1
        if sample.file_status != "OK":
            file_issues.append(f"{sample.identity.record_id}:{sample.file_status}")
        if sample.gold_tier not in {GoldTier.UNLABELED_CLEAN, GoldTier.QUARANTINE}:
            if not sample.annotation_provenance or not sample.annotation_provenance.strip():
                annotation_missing += 1
            if sample.normalization_version != NORMALIZATION_VERSION:
                blockers.add(f"NORMALIZATION_VERSION_MISSING_OR_INVALID:{sample.identity.record_id}")

    if not samples:
        blockers.add("NO_ELIGIBLE_SAMPLES")

    for issue in file_issues:
        blockers.add(f"FILE_STATUS:{issue}")
    if annotation_missing:
        blockers.add(f"ANNOTATION_PROVENANCE_MISSING:{annotation_missing}")

    split_records = [SplitRecord(sample.identity, sample.partition) for sample in samples]
    leakage = tuple(leakage_violations(split_records))
    for violation in leakage:
        blockers.add(f"LEAKAGE:{violation}")

    required = (Partition.TRAIN, Partition.VALIDATION, Partition.CALIBRATION, Partition.HOLDOUT)
    for partition in required:
        if split_counter[partition.value] == 0:
            blockers.add(f"REQUIRED_SPLIT_EMPTY:{partition.value}")

    for partition in (Partition.CALIBRATION, Partition.HOLDOUT):
        if not any(
            sample.partition is partition and sample.gold_tier in TEACHER_GOLD_TIERS
            for sample in samples
        ):
            blockers.add(f"TEACHER_GOLD_MISSING:{partition.value}")

    nonzero_classes = [count for count in class_counter.values() if count > 0]
    if len(nonzero_classes) >= 2:
        ratio = max(nonzero_classes) / min(nonzero_classes)
        if ratio > 10.0:
            warnings.add(f"CLASS_IMBALANCE_RATIO:{ratio:.2f}")

    corpus_counts = {
        corpus: len(work_ids)
        for corpus, work_ids in sorted(works_by_corpus.items())
    }
    duplicate_clusters = {
        cluster: count
        for cluster, count in sorted(duplicate_counter.items())
        if count > 1
    }

    training_authorized = not blockers
    return DatasetAuditReport(
        corpus_work_counts=corpus_counts,
        gold_tier_distribution=_sorted_counter(gold_counter),
        split_distribution=_sorted_counter(split_counter),
        duplicate_clusters=duplicate_clusters,
        leakage_violations=leakage,
        unresolved_licenses=unresolved_licenses,
        missing_hashes=missing_hashes,
        annotation_provenance_missing=annotation_missing,
        corrupt_or_unsupported=tuple(sorted(file_issues)),
        class_distribution=_sorted_counter(class_counter),
        ambiguous_gold_count=ambiguous_count,
        quarantined_sample_count=quarantined_count,
        candidate_sources_missing_manifests=missing_manifests,
        blockers=tuple(sorted(blockers)),
        warnings=tuple(sorted(warnings)),
        training_authorized=training_authorized,
    )


def audit_bundle(data: object) -> DatasetAuditReport:
    if not isinstance(data, dict):
        raise ValueError("audit bundle must be a JSON object")
    candidate_sources = data.get("candidate_sources")
    source_data = data.get("source_manifests")
    sample_data = data.get("samples")
    if not isinstance(candidate_sources, list) or not all(isinstance(x, str) and x.strip() for x in candidate_sources):
        raise ValueError("candidate_sources must be a list of non-empty strings")
    if not isinstance(source_data, list) or not all(isinstance(x, dict) for x in source_data):
        raise ValueError("source_manifests must be a list of objects")
    if not isinstance(sample_data, list) or not all(isinstance(x, dict) for x in sample_data):
        raise ValueError("samples must be a list of objects")
    manifests = [SourceManifest.from_dict(item) for item in source_data]
    samples = [AuditSample.from_dict(item) for item in sample_data]
    return audit_dataset(
        candidate_sources=candidate_sources,
        source_manifests=manifests,
        samples=samples,
    )
