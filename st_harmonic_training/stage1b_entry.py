from __future__ import annotations

import json

from .baseline_thresholds import THRESHOLD_SCHEMA
from .tavern_readiness_completion import COMPLETION_SCHEMA
from .tavern_structure import PINNED_TAVERN_REVISION

ENTRY_SCHEMA = "st-guitar-harmony-stage1b-entry-audit-v1"
EXPECTED_THRESHOLDS = {
    "EXACT_NORMALIZED_LABEL_MATCH": 0.10,
    "VARIANT_AWARE_ACCEPTABLE_SET_ACCURACY": 0.10,
    "ROMAN_NUMERAL_COMPONENT_ACCURACY": 0.15,
    "FUNCTIONAL_COMPONENT_ACCURACY": 0.10,
}
ENTRY_BLOCKERS = [
    "SCORE_INPUT_REALIZATION_PENDING",
    "DETERMINISTIC_FEATURE_SCHEMA_PENDING",
    "TRAINING_PAYLOAD_MANIFEST_PENDING",
    "MODEL_IMPLEMENTATION_PENDING",
]


class Stage1BEntryError(ValueError):
    pass


def build_stage1b_entry_audit(
    dataset_readiness: object,
    promotion_thresholds: object,
) -> dict[str, object]:
    if not isinstance(dataset_readiness, dict) or dataset_readiness.get("schema_version") != COMPLETION_SCHEMA:
        raise Stage1BEntryError("unsupported dataset readiness schema")
    if dataset_readiness.get("source_corpus") != "TAVERN_REVIEWED_694":
        raise Stage1BEntryError("dataset source subset mismatch")
    if dataset_readiness.get("source_revision") != PINNED_TAVERN_REVISION:
        raise Stage1BEntryError("dataset source revision mismatch")
    if dataset_readiness.get("dataset_readiness_gate") != "PASS":
        raise Stage1BEntryError("dataset readiness must PASS")
    if dataset_readiness.get("training_payload_ready") is not True:
        raise Stage1BEntryError("dataset target payload is not ready")
    if dataset_readiness.get("leakage_gate") != "PASS":
        raise Stage1BEntryError("leakage gate must PASS")
    if dataset_readiness.get("training_authorized") is not False:
        raise Stage1BEntryError("dataset stage must not pre-authorize training")

    if not isinstance(promotion_thresholds, dict) or promotion_thresholds.get("schema_version") != THRESHOLD_SCHEMA:
        raise Stage1BEntryError("unsupported promotion threshold schema")
    if promotion_thresholds.get("source_corpus") != "TAVERN_REVIEWED_694":
        raise Stage1BEntryError("threshold source subset mismatch")
    if promotion_thresholds.get("source_revision") != PINNED_TAVERN_REVISION:
        raise Stage1BEntryError("threshold source revision mismatch")
    if promotion_thresholds.get("promotion_threshold_status") != "FROZEN":
        raise Stage1BEntryError("promotion thresholds are not frozen")
    if promotion_thresholds.get("promotion_scope") != "OFFLINE_SHADOW_ONLY":
        raise Stage1BEntryError("promotion scope must remain offline shadow")
    if promotion_thresholds.get("validation_thresholds") != EXPECTED_THRESHOLDS:
        raise Stage1BEntryError("promotion thresholds changed")
    if promotion_thresholds.get("holdout_for_threshold_tuning") is not False:
        raise Stage1BEntryError("holdout threshold tuning is forbidden")
    if promotion_thresholds.get("calibration_for_threshold_tuning") is not False:
        raise Stage1BEntryError("calibration threshold tuning is forbidden")
    if promotion_thresholds.get("production_promotion_authorized") is not False:
        raise Stage1BEntryError("production promotion must remain disabled")
    if promotion_thresholds.get("training_authorized") is not False:
        raise Stage1BEntryError("threshold stage must not pre-authorize training")

    return {
        "schema_version": ENTRY_SCHEMA,
        "source_corpus": "TAVERN_REVIEWED_694",
        "source_revision": PINNED_TAVERN_REVISION,
        "dataset_readiness_gate": "PASS",
        "promotion_threshold_status": "FROZEN",
        "promotion_scope": "OFFLINE_SHADOW_ONLY",
        "leakage_gate": "PASS",
        "score_input_realization_complete": False,
        "deterministic_feature_schema_complete": False,
        "training_payload_manifest_complete": False,
        "model_implementation_complete": False,
        "blockers": ENTRY_BLOCKERS,
        "entry_gate_status": "HOLD",
        "model_training_started": False,
        "training_authorized": False,
        "production_authority": False,
    }


def canonical_stage1b_entry_json(data: dict[str, object]) -> str:
    if data.get("schema_version") != ENTRY_SCHEMA:
        raise Stage1BEntryError("unsupported Stage 1-B entry schema")
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
