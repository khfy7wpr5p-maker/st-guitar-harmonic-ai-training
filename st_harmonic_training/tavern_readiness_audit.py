from __future__ import annotations

import json
from typing import Any

from .normalization import NORMALIZATION_VERSION
from .tavern_gold_materialization import PINNED_VALIDATED_SHA256, SUMMARY_SCHEMA as MATERIALIZATION_SUMMARY_SCHEMA
from .tavern_reviewed_split import EXPECTED_RECORD_DISTRIBUTION, EXPECTED_SEED
from .tavern_structure import PINNED_TAVERN_REVISION

READINESS_SCHEMA = "st-tavern-final-readiness-audit-v1"
ADMISSION_SCHEMA = "st-tavern-reviewed-subset-admission-v1"
LINEAGE_SUMMARY_SCHEMA = "st-tavern-reviewed-lineage-closure-summary-v1"
SPLIT_SUMMARY_SCHEMA = "st-tavern-reviewed-split-summary-v1"
EXPECTED_RECORD_COUNT = 694
EXPECTED_GOLD_COUNTS = {"GOLD_EXPERT": 641, "GOLD_VARIANT": 53}
EXPECTED_FAMILY_COUNTS = {"CALIBRATION": 2, "HOLDOUT": 2, "TRAIN": 18, "VALIDATION": 2}


class TavernReadinessAuditError(ValueError):
    pass


def _require_dict(data: object, schema: str, label: str) -> dict[str, Any]:
    if not isinstance(data, dict) or data.get("schema_version") != schema:
        raise TavernReadinessAuditError(f"unsupported {label} schema")
    return data


def _require_common(data: dict[str, Any], *, corpus: str | None = None) -> None:
    if data.get("source_revision") != PINNED_TAVERN_REVISION:
        raise TavernReadinessAuditError("source revision mismatch")
    if corpus is not None and data.get("source_corpus") != corpus:
        raise TavernReadinessAuditError("source corpus mismatch")
    if data.get("training_authorized") is not False:
        raise TavernReadinessAuditError("upstream stage must not pre-authorize training")


def build_tavern_final_readiness_audit(
    materialization_summary: object,
    admission_summary: object,
    lineage_summary: object,
    split_summary: object,
) -> dict[str, object]:
    material = _require_dict(materialization_summary, MATERIALIZATION_SUMMARY_SCHEMA, "materialization")
    admission = _require_dict(admission_summary, ADMISSION_SCHEMA, "admission")
    lineage = _require_dict(lineage_summary, LINEAGE_SUMMARY_SCHEMA, "lineage")
    split = _require_dict(split_summary, SPLIT_SUMMARY_SCHEMA, "split")

    _require_common(material, corpus="TAVERN")
    _require_common(admission)
    _require_common(lineage, corpus="TAVERN_REVIEWED_694")
    _require_common(split, corpus="TAVERN_REVIEWED_694")

    if material.get("validated_human_decisions_sha256") != PINNED_VALIDATED_SHA256:
        raise TavernReadinessAuditError("materialization digest mismatch")
    if material.get("record_count") != EXPECTED_RECORD_COUNT or material.get("gold_tier_counts") != EXPECTED_GOLD_COUNTS:
        raise TavernReadinessAuditError("materialized gold count/distribution mismatch")
    if material.get("normalization_version") != NORMALIZATION_VERSION:
        raise TavernReadinessAuditError("normalization version mismatch")
    if material.get("gold_assignment_authorized") is not True:
        raise TavernReadinessAuditError("teacher-gold assignment is not authorized")
    if material.get("partition_assignment_authorized") is not False:
        raise TavernReadinessAuditError("materialization unexpectedly assigns partitions")

    if admission.get("subset_corpus") != "TAVERN_REVIEWED_694":
        raise TavernReadinessAuditError("reviewed subset corpus mismatch")
    if admission.get("admitted_record_count") != EXPECTED_RECORD_COUNT or admission.get("excluded_record_count") != 243:
        raise TavernReadinessAuditError("admission counts mismatch")
    if admission.get("gold_tier_counts") != EXPECTED_GOLD_COUNTS:
        raise TavernReadinessAuditError("admission gold distribution mismatch")
    if admission.get("admission_scope") != "DATASET_ENGINEERING_ONLY":
        raise TavernReadinessAuditError("admission scope mismatch")
    if admission.get("partition_assignment_authorized") is not False:
        raise TavernReadinessAuditError("admission unexpectedly assigns partitions")
    raw_complete = admission.get("raw_label_realization_complete")
    normalization_complete = admission.get("normalization_complete")
    if not isinstance(raw_complete, bool) or not isinstance(normalization_complete, bool):
        raise TavernReadinessAuditError("readiness booleans are malformed")

    if lineage.get("validated_human_decisions_sha256") != PINNED_VALIDATED_SHA256:
        raise TavernReadinessAuditError("lineage digest mismatch")
    if lineage.get("reviewed_record_count") != EXPECTED_RECORD_COUNT or lineage.get("active_work_family_count") != 24:
        raise TavernReadinessAuditError("lineage counts mismatch")
    if lineage.get("inactive_documented_work_ids") != ["Beethoven/B071", "Mozart/K025", "Mozart/K179"]:
        raise TavernReadinessAuditError("inactive work-family set mismatch")
    if lineage.get("cross_corpus_aliases_bound") is not True:
        raise TavernReadinessAuditError("cross-corpus lineage aliases are not bound")
    if lineage.get("partition_assignment_authorized") is not False:
        raise TavernReadinessAuditError("lineage unexpectedly assigns partitions")

    if split.get("validated_human_decisions_sha256") != PINNED_VALIDATED_SHA256:
        raise TavernReadinessAuditError("split digest mismatch")
    if split.get("record_count") != EXPECTED_RECORD_COUNT:
        raise TavernReadinessAuditError("split record count mismatch")
    if split.get("seed") != EXPECTED_SEED or split.get("label_aware_seed_selection") is not False:
        raise TavernReadinessAuditError("split seed/policy mismatch")
    if split.get("record_distribution") != EXPECTED_RECORD_DISTRIBUTION:
        raise TavernReadinessAuditError("split record distribution mismatch")
    if split.get("work_family_distribution") != EXPECTED_FAMILY_COUNTS:
        raise TavernReadinessAuditError("split work-family distribution mismatch")
    if split.get("cross_corpus_alias_partition_inheritance_required") is not True:
        raise TavernReadinessAuditError("cross-corpus partition inheritance is not enforced")
    if split.get("augmentation_scope") != "TRAIN_ONLY":
        raise TavernReadinessAuditError("augmentation scope must be TRAIN_ONLY")
    if split.get("partition_assignment_authorized") is not True:
        raise TavernReadinessAuditError("split partition assignment is not authorized")

    blockers: list[str] = []
    if not raw_complete:
        blockers.append("RAW_LABEL_REALIZATION_PENDING")
    if not normalization_complete:
        blockers.append("DETERMINISTIC_NORMALIZATION_PENDING")

    training_authorized = not blockers
    return {
        "schema_version": READINESS_SCHEMA,
        "source_corpus": "TAVERN_REVIEWED_694",
        "source_revision": PINNED_TAVERN_REVISION,
        "validated_human_decisions_sha256": PINNED_VALIDATED_SHA256,
        "eligible_record_count": EXPECTED_RECORD_COUNT,
        "quarantined_review_record_count": 243,
        "gold_tier_counts": EXPECTED_GOLD_COUNTS,
        "work_family_count": 24,
        "split_seed": EXPECTED_SEED,
        "split_distribution": EXPECTED_RECORD_DISTRIBUTION,
        "teacher_gold_present_in_calibration": EXPECTED_RECORD_DISTRIBUTION["CALIBRATION"] > 0,
        "teacher_gold_present_in_holdout": EXPECTED_RECORD_DISTRIBUTION["HOLDOUT"] > 0,
        "cross_corpus_lineage_bound": True,
        "leakage_gate": "PASS",
        "raw_label_realization_complete": raw_complete,
        "normalization_complete": normalization_complete,
        "blockers": blockers,
        "gate_status": "PASS" if training_authorized else "HOLD",
        "training_authorized": training_authorized,
    }


def canonical_tavern_readiness_audit_json(data: dict[str, object]) -> str:
    if data.get("schema_version") != READINESS_SCHEMA:
        raise TavernReadinessAuditError("unsupported readiness audit schema")
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
