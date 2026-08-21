from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re
from typing import Any

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class AcquisitionStatus(StrEnum):
    READY = "READY"
    QUARANTINE = "QUARANTINE"


class GoldTier(StrEnum):
    GOLD_CONSENSUS = "GOLD_CONSENSUS"
    GOLD_EXPERT = "GOLD_EXPERT"
    GOLD_VARIANT = "GOLD_VARIANT"
    SILVER_REVIEWED = "SILVER_REVIEWED"
    SILVER_AUTO = "SILVER_AUTO"
    UNLABELED_CLEAN = "UNLABELED_CLEAN"
    QUARANTINE = "QUARANTINE"


class AdjudicationOutcome(StrEnum):
    RESOLVED = "RESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    ABSTAIN = "ABSTAIN"


class AnnotationKind(StrEnum):
    HUMAN_CONSENSUS = "HUMAN_CONSENSUS"
    HUMAN_EXPERT = "HUMAN_EXPERT"
    HUMAN_VARIANT = "HUMAN_VARIANT"
    HUMAN_REVIEWED = "HUMAN_REVIEWED"
    AUTO = "AUTO"
    UNLABELED = "UNLABELED"


TEACHER_GOLD_TIERS = {
    GoldTier.GOLD_CONSENSUS,
    GoldTier.GOLD_EXPERT,
    GoldTier.GOLD_VARIANT,
}

ALLOWED_GOLD_PROVENANCE = {
    GoldTier.GOLD_CONSENSUS: {AnnotationKind.HUMAN_CONSENSUS},
    GoldTier.GOLD_EXPERT: {AnnotationKind.HUMAN_EXPERT},
    GoldTier.GOLD_VARIANT: {AnnotationKind.HUMAN_VARIANT},
    GoldTier.SILVER_REVIEWED: {AnnotationKind.HUMAN_REVIEWED},
    GoldTier.SILVER_AUTO: {AnnotationKind.AUTO},
    GoldTier.UNLABELED_CLEAN: {AnnotationKind.UNLABELED},
    GoldTier.QUARANTINE: set(AnnotationKind),
}


class ContractError(ValueError):
    pass


def _required_text(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{key} must be a non-empty string")
    return value.strip()


def _optional_sha256(data: dict[str, Any], key: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise ContractError(f"{key} must be lowercase SHA-256 hex or null")
    return value


@dataclass(frozen=True)
class SourceManifest:
    source_corpus: str
    source_url: str
    immutable_revision: str
    release_tag_commit_doi: str
    raw_archive_sha256: str | None
    score_sha256: str | None
    analysis_sha256: str | None
    license_id: str
    license_scope: str
    source_provenance: str
    annotation_provenance: str
    known_issues: tuple[str, ...]
    acquisition_status: AcquisitionStatus
    quarantine_reason: str | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SourceManifest":
        status = AcquisitionStatus(_required_text(data, "acquisition_status"))
        known_issues = data.get("known_issues")
        if not isinstance(known_issues, list) or not all(isinstance(x, str) for x in known_issues):
            raise ContractError("known_issues must be an array of strings")
        quarantine_reason = data.get("quarantine_reason")
        if quarantine_reason is not None and (not isinstance(quarantine_reason, str) or not quarantine_reason.strip()):
            raise ContractError("quarantine_reason must be null or a non-empty string")

        manifest = cls(
            source_corpus=_required_text(data, "source_corpus"),
            source_url=_required_text(data, "source_url"),
            immutable_revision=_required_text(data, "immutable_revision"),
            release_tag_commit_doi=_required_text(data, "release_tag_commit_doi"),
            raw_archive_sha256=_optional_sha256(data, "raw_archive_sha256"),
            score_sha256=_optional_sha256(data, "score_sha256"),
            analysis_sha256=_optional_sha256(data, "analysis_sha256"),
            license_id=_required_text(data, "license_id"),
            license_scope=_required_text(data, "license_scope"),
            source_provenance=_required_text(data, "source_provenance"),
            annotation_provenance=_required_text(data, "annotation_provenance"),
            known_issues=tuple(known_issues),
            acquisition_status=status,
            quarantine_reason=quarantine_reason.strip() if isinstance(quarantine_reason, str) else None,
        )
        manifest.validate()
        return manifest

    def validate(self) -> None:
        if self.acquisition_status is AcquisitionStatus.READY:
            missing = [
                name
                for name, value in (
                    ("raw_archive_sha256", self.raw_archive_sha256),
                    ("score_sha256", self.score_sha256),
                    ("analysis_sha256", self.analysis_sha256),
                )
                if value is None
            ]
            if missing:
                raise ContractError("READY source missing hashes: " + ", ".join(missing))
            if self.license_id.upper() in {"UNKNOWN", "UNRESOLVED", "NONE"}:
                raise ContractError("READY source cannot have unresolved license")
            if self.quarantine_reason is not None:
                raise ContractError("READY source cannot carry quarantine_reason")
        else:
            if not self.quarantine_reason:
                raise ContractError("QUARANTINE source requires quarantine_reason")


@dataclass(frozen=True)
class GoldRecord:
    record_id: str
    gold_tier: GoldTier
    annotation_kind: AnnotationKind
    adjudication_outcome: AdjudicationOutcome
    raw_source_label: str | None
    annotator_count: int
    notes: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GoldRecord":
        record_id = _required_text(data, "record_id")
        tier = GoldTier(_required_text(data, "gold_tier"))
        kind = AnnotationKind(_required_text(data, "annotation_kind"))
        outcome = AdjudicationOutcome(_required_text(data, "adjudication_outcome"))
        raw = data.get("raw_source_label")
        if raw is not None and not isinstance(raw, str):
            raise ContractError("raw_source_label must be string or null")
        annotator_count = data.get("annotator_count")
        if not isinstance(annotator_count, int) or annotator_count < 0:
            raise ContractError("annotator_count must be a non-negative integer")
        notes = data.get("notes")
        if notes is not None and not isinstance(notes, str):
            raise ContractError("notes must be string or null")
        record = cls(record_id, tier, kind, outcome, raw, annotator_count, notes)
        record.validate()
        return record

    def validate(self) -> None:
        if self.annotation_kind not in ALLOWED_GOLD_PROVENANCE[self.gold_tier]:
            raise ContractError(
                f"{self.annotation_kind} cannot produce tier {self.gold_tier}"
            )
        if self.gold_tier in TEACHER_GOLD_TIERS and self.annotator_count < 1:
            raise ContractError("teacher-gold requires at least one human annotator")
        if self.annotation_kind is AnnotationKind.AUTO and self.gold_tier in TEACHER_GOLD_TIERS:
            raise ContractError("automatic annotation cannot become teacher-gold without human validation")
        if self.adjudication_outcome in {AdjudicationOutcome.AMBIGUOUS, AdjudicationOutcome.ABSTAIN}:
            if self.gold_tier is GoldTier.SILVER_AUTO:
                raise ContractError("automatic-only records cannot establish gold ambiguity/adjudication")
