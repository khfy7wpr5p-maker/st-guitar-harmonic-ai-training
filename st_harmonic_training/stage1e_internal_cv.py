from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import stat
from typing import Any

from .safe_ingest import load_bounded_json
from .split import Partition, deterministic_partition
from .tavern_lineage import _work_mapping
from .tavern_lineage_closure import EXPECTED_INACTIVE_DOCUMENTED_WORKS
from .tavern_reviewed_split import EXPECTED_RECORD_DISTRIBUTION, EXPECTED_SEED
from .tavern_structure import DOCUMENTED_WORK_IDS, PINNED_TAVERN_REVISION
from .training_payload import (
    PAYLOAD_SCHEMA,
    PINNED_TRAINING_PAYLOAD_MANIFEST_SHA256,
)

GROUP_PLAN_SCHEMA = "st-stage1e-train-only-group-plan-v1"
MATERIALIZED_SCHEMA = "st-stage1e-train-only-internal-cv-v1"
SUMMARY_SCHEMA = "st-stage1e-train-only-internal-cv-summary-v1"
DEVELOPMENT_SEED = "st-stage1e-grouped-cv-v1"
ASSIGNMENT_POLICY = "SHA256_RANK_ROUND_ROBIN_IDENTITY_ONLY"
FOLD_COUNT = 3
EXPECTED_TRAIN_RECORD_COUNT = 487
EXPECTED_TRAIN_WORK_FAMILY_COUNT = 18
EXPECTED_GROUPS_PER_FOLD = 6
PINNED_GROUP_PLAN_SHA256 = (
    "ae15ed507247548907815f8ee1a5586f9fa2384a32d5102e887ddedff52e1a4c"
)
MAX_INPUT_BYTES = 8 * 1024 * 1024


class Stage1EInternalCVError(ValueError):
    pass


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _active_canonical_work_ids() -> list[str]:
    active = DOCUMENTED_WORK_IDS - EXPECTED_INACTIVE_DOCUMENTED_WORKS
    canonical = sorted(str(_work_mapping(work)["canonical_work_id"]) for work in active)
    if len(canonical) != 24 or len(canonical) != len(set(canonical)):
        raise Stage1EInternalCVError("active canonical work-family set changed")
    return canonical


def expected_stage0_train_groups() -> tuple[str, ...]:
    groups = tuple(
        group
        for group in _active_canonical_work_ids()
        if deterministic_partition(group, seed=EXPECTED_SEED) is Partition.TRAIN
    )
    if len(groups) != EXPECTED_TRAIN_WORK_FAMILY_COUNT:
        raise Stage1EInternalCVError("Stage 0-T TRAIN work-family count changed")
    return groups


def _rank_key(group: str) -> tuple[str, str]:
    digest = hashlib.sha256(f"{DEVELOPMENT_SEED}\x1f{group}".encode("utf-8")).hexdigest()
    return digest, group


def build_stage1e_group_plan() -> dict[str, object]:
    groups = expected_stage0_train_groups()
    ranked = sorted(groups, key=_rank_key)
    assignment = {group: index % FOLD_COUNT for index, group in enumerate(ranked)}
    records = [
        {"split_group_id": group, "development_fold": assignment[group]}
        for group in sorted(groups)
    ]
    counts = Counter(int(item["development_fold"]) for item in records)
    expected_counts = {str(index): EXPECTED_GROUPS_PER_FOLD for index in range(FOLD_COUNT)}
    observed_counts = {str(index): counts[index] for index in range(FOLD_COUNT)}
    if observed_counts != expected_counts:
        raise Stage1EInternalCVError("grouped CV family distribution changed")
    manifest_sha256 = _canonical_sha256(records)
    if manifest_sha256 != PINNED_GROUP_PLAN_SHA256:
        raise Stage1EInternalCVError("pinned Stage 1-E group plan digest changed")
    return {
        "schema_version": GROUP_PLAN_SCHEMA,
        "source_corpus": "TAVERN_REVIEWED_694",
        "source_revision": PINNED_TAVERN_REVISION,
        "source_stage0_split_seed": EXPECTED_SEED,
        "eligible_partition": "TRAIN",
        "development_seed": DEVELOPMENT_SEED,
        "assignment_policy": ASSIGNMENT_POLICY,
        "fold_count": FOLD_COUNT,
        "work_family_count": len(records),
        "work_family_distribution": observed_counts,
        "group_plan_manifest_sha256": manifest_sha256,
        "groups": records,
        "label_aware_assignment": False,
        "original_validation_access": False,
        "calibration_access": False,
        "holdout_access": False,
        "quarantine_access": False,
        "event_target_materialization_authorized": False,
        "model_training_started": False,
        "training_authorized": False,
        "production_authority": False,
    }


def _validate_source_payload(
    data: object,
    *,
    expected_source_payload_sha256: str,
) -> list[dict[str, Any]]:
    if not isinstance(data, dict) or data.get("schema_version") != PAYLOAD_SCHEMA:
        raise Stage1EInternalCVError("unsupported training payload schema")
    if data.get("source_corpus") != "TAVERN_REVIEWED_694":
        raise Stage1EInternalCVError("source corpus mismatch")
    if data.get("source_revision") != PINNED_TAVERN_REVISION:
        raise Stage1EInternalCVError("source revision mismatch")
    if data.get("training_payload_manifest_sha256") != expected_source_payload_sha256:
        raise Stage1EInternalCVError("training payload manifest digest mismatch")
    if data.get("partition_distribution") != EXPECTED_RECORD_DISTRIBUTION:
        raise Stage1EInternalCVError("source partition distribution changed")
    if data.get("augmentation_scope") != "TRAIN_ONLY":
        raise Stage1EInternalCVError("augmentation scope must remain TRAIN_ONLY")
    if data.get("cross_corpus_alias_partition_inheritance_required") is not True:
        raise Stage1EInternalCVError("cross-corpus lineage inheritance is not enforced")
    if data.get("holdout_labels_available_to_training") is not False:
        raise Stage1EInternalCVError("HOLDOUT label access unexpectedly enabled")
    if data.get("holdout_labels_available_to_model_selection") is not False:
        raise Stage1EInternalCVError("HOLDOUT model-selection access unexpectedly enabled")
    if data.get("calibration_labels_available_to_parameter_fitting") is not False:
        raise Stage1EInternalCVError("CALIBRATION fitting access unexpectedly enabled")
    records = data.get("records")
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        raise Stage1EInternalCVError("training payload records malformed")
    if len(records) != sum(EXPECTED_RECORD_DISTRIBUTION.values()):
        raise Stage1EInternalCVError("training payload record count changed")
    if _canonical_sha256(records) != expected_source_payload_sha256:
        raise Stage1EInternalCVError("training payload record body digest mismatch")
    return records


def materialize_stage1e_internal_cv(
    data: object,
    *,
    expected_source_payload_sha256: str = PINNED_TRAINING_PAYLOAD_MANIFEST_SHA256,
) -> dict[str, object]:
    records = _validate_source_payload(
        data, expected_source_payload_sha256=expected_source_payload_sha256
    )
    plan = build_stage1e_group_plan()
    fold_by_group = {
        str(item["split_group_id"]): int(item["development_fold"])
        for item in plan["groups"]
    }
    expected_train_groups = set(fold_by_group)

    seen_phrases: set[str] = set()
    source_partition_counts: Counter[str] = Counter()
    group_partitions: dict[str, set[str]] = defaultdict(set)
    train_rows: list[dict[str, object]] = []
    train_groups: set[str] = set()

    for item in records:
        phrase = item.get("phrase_key")
        partition = item.get("partition")
        group = item.get("split_group_id")
        canonical = item.get("canonical_work_id")
        if not isinstance(phrase, str) or not phrase:
            raise Stage1EInternalCVError("source record missing phrase_key")
        if phrase in seen_phrases:
            raise Stage1EInternalCVError(f"duplicate phrase_key: {phrase}")
        seen_phrases.add(phrase)
        if partition not in {"TRAIN", "VALIDATION", "CALIBRATION", "HOLDOUT"}:
            raise Stage1EInternalCVError(f"unsupported source partition: {partition}")
        if not isinstance(group, str) or not group:
            raise Stage1EInternalCVError(f"missing split_group_id for {phrase}")
        if not isinstance(canonical, str) or canonical != group:
            raise Stage1EInternalCVError(f"canonical/split-group mismatch for {phrase}")
        source_partition_counts[str(partition)] += 1
        group_partitions[group].add(str(partition))
        if partition != "TRAIN":
            continue
        if group not in expected_train_groups:
            raise Stage1EInternalCVError(
                f"non-Stage0-TRAIN family appeared in Stage 1-E source: {group}"
            )
        train_groups.add(group)
        train_rows.append(
            {
                "phrase_key": phrase,
                "canonical_work_id": canonical,
                "split_group_id": group,
                "development_fold": fold_by_group[group],
            }
        )

    observed_source = {
        key: source_partition_counts[key] for key in sorted(source_partition_counts)
    }
    if observed_source != EXPECTED_RECORD_DISTRIBUTION:
        raise Stage1EInternalCVError("observed source partition counts changed")
    leakage = {
        group: sorted(values)
        for group, values in group_partitions.items()
        if len(values) != 1
    }
    if leakage:
        raise Stage1EInternalCVError(f"source split group spans partitions: {leakage}")
    if len(train_rows) != EXPECTED_TRAIN_RECORD_COUNT:
        raise Stage1EInternalCVError("Stage 1-E TRAIN record count changed")
    if train_groups != expected_train_groups:
        raise Stage1EInternalCVError("Stage 1-E TRAIN work-family set changed")

    train_rows.sort(key=lambda item: str(item["phrase_key"]))
    fold_record_counts = Counter(int(item["development_fold"]) for item in train_rows)
    record_distribution = {
        str(index): fold_record_counts[index] for index in range(FOLD_COUNT)
    }
    manifest_sha256 = _canonical_sha256(train_rows)

    return {
        "schema_version": MATERIALIZED_SCHEMA,
        "source_corpus": "TAVERN_REVIEWED_694",
        "source_revision": PINNED_TAVERN_REVISION,
        "source_training_payload_manifest_sha256": expected_source_payload_sha256,
        "source_stage0_split_seed": EXPECTED_SEED,
        "eligible_partition": "TRAIN",
        "development_seed": DEVELOPMENT_SEED,
        "assignment_policy": ASSIGNMENT_POLICY,
        "fold_count": FOLD_COUNT,
        "work_family_count": len(train_groups),
        "record_count": len(train_rows),
        "work_family_distribution": plan["work_family_distribution"],
        "record_distribution": record_distribution,
        "group_plan_manifest_sha256": plan["group_plan_manifest_sha256"],
        "record_assignment_manifest_sha256": manifest_sha256,
        "records": train_rows,
        "label_aware_assignment": False,
        "augmentation_scope": "INTERNAL_TRAIN_SIDE_ONLY",
        "original_validation_access": False,
        "calibration_access": False,
        "holdout_access": False,
        "quarantine_access": False,
        "event_target_materialization_authorized": False,
        "model_training_started": False,
        "training_authorized": False,
        "production_authority": False,
    }


def build_stage1e_summary(data: object) -> dict[str, object]:
    if not isinstance(data, dict) or data.get("schema_version") != MATERIALIZED_SCHEMA:
        raise Stage1EInternalCVError("unsupported Stage 1-E materialization schema")
    if data.get("record_count") != EXPECTED_TRAIN_RECORD_COUNT:
        raise Stage1EInternalCVError("Stage 1-E record count mismatch")
    if data.get("work_family_count") != EXPECTED_TRAIN_WORK_FAMILY_COUNT:
        raise Stage1EInternalCVError("Stage 1-E work-family count mismatch")
    for field in (
        "original_validation_access",
        "calibration_access",
        "holdout_access",
        "quarantine_access",
        "event_target_materialization_authorized",
        "model_training_started",
        "training_authorized",
        "production_authority",
    ):
        if data.get(field) is not False:
            raise Stage1EInternalCVError(f"Stage 1-E authority boundary violated: {field}")
    fields = (
        "source_corpus",
        "source_revision",
        "source_training_payload_manifest_sha256",
        "source_stage0_split_seed",
        "eligible_partition",
        "development_seed",
        "assignment_policy",
        "fold_count",
        "work_family_count",
        "record_count",
        "work_family_distribution",
        "record_distribution",
        "group_plan_manifest_sha256",
        "record_assignment_manifest_sha256",
        "label_aware_assignment",
        "augmentation_scope",
        "original_validation_access",
        "calibration_access",
        "holdout_access",
        "quarantine_access",
        "event_target_materialization_authorized",
        "model_training_started",
        "training_authorized",
        "production_authority",
    )
    summary: dict[str, object] = {"schema_version": SUMMARY_SCHEMA}
    summary.update({field: data[field] for field in fields})
    return summary


def build_stage1e_group_plan_summary() -> dict[str, object]:
    plan = build_stage1e_group_plan()
    return {
        "schema_version": "st-stage1e-train-only-group-plan-summary-v1",
        "source_corpus": plan["source_corpus"],
        "source_revision": plan["source_revision"],
        "source_training_payload_manifest_sha256": PINNED_TRAINING_PAYLOAD_MANIFEST_SHA256,
        "source_stage0_split_seed": plan["source_stage0_split_seed"],
        "eligible_partition": plan["eligible_partition"],
        "development_seed": plan["development_seed"],
        "assignment_policy": plan["assignment_policy"],
        "fold_count": plan["fold_count"],
        "work_family_count": plan["work_family_count"],
        "work_family_distribution": plan["work_family_distribution"],
        "group_plan_manifest_sha256": plan["group_plan_manifest_sha256"],
        "label_aware_assignment": False,
        "record_materialization_status": "PENDING_PRIVATE_PAYLOAD",
        "original_validation_access": False,
        "calibration_access": False,
        "holdout_access": False,
        "quarantine_access": False,
        "event_target_materialization_authorized": False,
        "model_training_started": False,
        "training_authorized": False,
        "production_authority": False,
    }


def materialize_stage1e_internal_cv_from_file(path: str | Path) -> dict[str, object]:
    p = Path(path)
    if p.is_symlink():
        raise Stage1EInternalCVError("symlink input rejected")
    meta = p.stat()
    if not stat.S_ISREG(meta.st_mode) or meta.st_size > MAX_INPUT_BYTES:
        raise Stage1EInternalCVError("input must be a bounded regular file")
    return materialize_stage1e_internal_cv(
        load_bounded_json(p, max_bytes=MAX_INPUT_BYTES)
    )


def canonical_stage1e_json(data: dict[str, object]) -> str:
    if data.get("schema_version") not in {
        GROUP_PLAN_SCHEMA,
        MATERIALIZED_SCHEMA,
        SUMMARY_SCHEMA,
        "st-stage1e-train-only-group-plan-summary-v1",
    }:
        raise Stage1EInternalCVError("unsupported Stage 1-E schema")
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
