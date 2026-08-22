from __future__ import annotations

import json
from typing import Any

from .baseline_thresholds import THRESHOLD_SCHEMA
from .sparse_nb_model import (
    MODEL_IMPLEMENTATION_VERSION,
    MODEL_SEED,
    SCORE_SEMANTICS,
)
from .tavern_kern_features import (
    ADAPTER_VERSION as FEATURE_ADAPTER_VERSION,
    SUMMARY_SCHEMA as FEATURE_SUMMARY_SCHEMA,
)
from .tavern_readiness_completion import COMPLETION_SCHEMA
from .tavern_score_input_realization import SUMMARY_SCHEMA as SCORE_SUMMARY_SCHEMA
from .tavern_structure import PINNED_TAVERN_REVISION
from .training_payload import (
    PINNED_TRAINING_PAYLOAD_MANIFEST_SHA256,
    SUMMARY_SCHEMA as PAYLOAD_SUMMARY_SCHEMA,
)

ENTRY_COMPLETION_SCHEMA = "st-guitar-harmony-stage1b-entry-completion-v1"
MODEL_EVIDENCE_SCHEMA = "st-guitar-harmony-model-implementation-evidence-v1"
ENVIRONMENT_LOCK_SCHEMA = "st-guitar-harmony-model-environment-lock-v1"
EXPECTED_SOURCE = "TAVERN_REVIEWED_694"
EXPECTED_RECORD_COUNT = 694
EXPECTED_TARGET_COUNT = 747
EXPECTED_PARTITIONS = {
    "CALIBRATION": 41,
    "HOLDOUT": 41,
    "TRAIN": 487,
    "VALIDATION": 125,
}
EXPECTED_THRESHOLDS = {
    "EXACT_NORMALIZED_LABEL_MATCH": 0.10,
    "VARIANT_AWARE_ACCEPTABLE_SET_ACCURACY": 0.10,
    "ROMAN_NUMERAL_COMPONENT_ACCURACY": 0.15,
    "FUNCTIONAL_COMPONENT_ACCURACY": 0.10,
}
EXPECTED_SCORE_INPUT_MANIFEST_SHA256 = (
    "de394ddcbbb18326b1fc91f162be9fa79eb515cd8e522dab915e79669d42075d"
)
EXPECTED_FEATURE_MANIFEST_SHA256 = (
    "184ea471894ff6cf376255d62e1f348c0878dc4c53939289b95fae40cb261126"
)
EXPECTED_NORMALIZED_TARGET_MANIFEST_SHA256 = (
    "195ec1ce2193f8560043a94f3ea99c8db69b830fff6e60313c88565714450a4c"
)


class Stage1BEntryCompletionError(ValueError):
    pass


def _require_dict(data: object, schema: str, label: str) -> dict[str, Any]:
    if not isinstance(data, dict) or data.get("schema_version") != schema:
        raise Stage1BEntryCompletionError(f"unsupported {label} schema")
    return data


def _require_identity(data: dict[str, Any], label: str) -> None:
    if data.get("source_corpus") != EXPECTED_SOURCE:
        raise Stage1BEntryCompletionError(f"{label} source subset mismatch")
    if data.get("source_revision") != PINNED_TAVERN_REVISION:
        raise Stage1BEntryCompletionError(f"{label} source revision mismatch")


def build_stage1b_entry_completion(
    dataset_readiness: object,
    promotion_thresholds: object,
    score_summary: object,
    feature_summary: object,
    payload_summary: object,
    model_evidence: object,
    environment_lock: object,
) -> dict[str, object]:
    dataset = _require_dict(dataset_readiness, COMPLETION_SCHEMA, "dataset readiness")
    thresholds = _require_dict(promotion_thresholds, THRESHOLD_SCHEMA, "promotion thresholds")
    score = _require_dict(score_summary, SCORE_SUMMARY_SCHEMA, "score input")
    feature = _require_dict(feature_summary, FEATURE_SUMMARY_SCHEMA, "feature")
    payload = _require_dict(payload_summary, PAYLOAD_SUMMARY_SCHEMA, "training payload")
    model = _require_dict(model_evidence, MODEL_EVIDENCE_SCHEMA, "model implementation")
    environment = _require_dict(environment_lock, ENVIRONMENT_LOCK_SCHEMA, "environment lock")

    for data, label in (
        (dataset, "dataset readiness"),
        (thresholds, "promotion thresholds"),
        (score, "score input"),
        (feature, "feature"),
        (payload, "training payload"),
    ):
        _require_identity(data, label)

    if dataset.get("dataset_readiness_gate") != "PASS":
        raise Stage1BEntryCompletionError("dataset readiness must PASS")
    if dataset.get("leakage_gate") != "PASS":
        raise Stage1BEntryCompletionError("leakage gate must PASS")
    if dataset.get("training_payload_ready") is not True:
        raise Stage1BEntryCompletionError("dataset target payload is not ready")
    if dataset.get("training_authorized") is not False:
        raise Stage1BEntryCompletionError("dataset stage must not pre-authorize training")

    if thresholds.get("promotion_threshold_status") != "FROZEN":
        raise Stage1BEntryCompletionError("promotion thresholds must be frozen")
    if thresholds.get("promotion_scope") != "OFFLINE_SHADOW_ONLY":
        raise Stage1BEntryCompletionError("promotion scope changed")
    if thresholds.get("validation_thresholds") != EXPECTED_THRESHOLDS:
        raise Stage1BEntryCompletionError("validation thresholds changed")
    if thresholds.get("holdout_for_threshold_tuning") is not False:
        raise Stage1BEntryCompletionError("holdout threshold tuning is forbidden")
    if thresholds.get("calibration_for_threshold_tuning") is not False:
        raise Stage1BEntryCompletionError("calibration threshold tuning is forbidden")
    if thresholds.get("production_promotion_authorized") is not False:
        raise Stage1BEntryCompletionError("production promotion must remain disabled")

    if score.get("record_count") != EXPECTED_RECORD_COUNT:
        raise Stage1BEntryCompletionError("score record count mismatch")
    if score.get("score_input_realization_complete") is not True:
        raise Stage1BEntryCompletionError("score realization incomplete")
    if score.get("score_input_manifest_sha256") != EXPECTED_SCORE_INPUT_MANIFEST_SHA256:
        raise Stage1BEntryCompletionError("score input manifest changed")
    if score.get("training_authorized") is not False:
        raise Stage1BEntryCompletionError("score stage must not authorize training")

    if feature.get("record_count") != EXPECTED_RECORD_COUNT:
        raise Stage1BEntryCompletionError("feature record count mismatch")
    if feature.get("adapter_version") != FEATURE_ADAPTER_VERSION:
        raise Stage1BEntryCompletionError("feature adapter version changed")
    if feature.get("feature_manifest_sha256") != EXPECTED_FEATURE_MANIFEST_SHA256:
        raise Stage1BEntryCompletionError("feature manifest changed")
    if feature.get("score_input_manifest_sha256") != EXPECTED_SCORE_INPUT_MANIFEST_SHA256:
        raise Stage1BEntryCompletionError("feature/score evidence disagreement")
    if feature.get("deterministic_feature_schema_complete") is not True:
        raise Stage1BEntryCompletionError("deterministic feature schema incomplete")
    if feature.get("training_authorized") is not False:
        raise Stage1BEntryCompletionError("feature stage must not authorize training")

    if payload.get("record_count") != EXPECTED_RECORD_COUNT:
        raise Stage1BEntryCompletionError("payload record count mismatch")
    if payload.get("target_count") != EXPECTED_TARGET_COUNT:
        raise Stage1BEntryCompletionError("payload target count mismatch")
    if payload.get("partition_distribution") != EXPECTED_PARTITIONS:
        raise Stage1BEntryCompletionError("payload partition distribution changed")
    if payload.get("feature_manifest_sha256") != EXPECTED_FEATURE_MANIFEST_SHA256:
        raise Stage1BEntryCompletionError("payload feature manifest changed")
    if payload.get("normalized_target_manifest_sha256") != EXPECTED_NORMALIZED_TARGET_MANIFEST_SHA256:
        raise Stage1BEntryCompletionError("payload target manifest changed")
    if payload.get("training_payload_manifest_sha256") != PINNED_TRAINING_PAYLOAD_MANIFEST_SHA256:
        raise Stage1BEntryCompletionError("training payload manifest changed")
    if payload.get("training_payload_manifest_complete") is not True:
        raise Stage1BEntryCompletionError("training payload manifest incomplete")
    if payload.get("holdout_labels_available_to_training") is not False:
        raise Stage1BEntryCompletionError("holdout labels exposed to training")
    if payload.get("holdout_labels_available_to_model_selection") is not False:
        raise Stage1BEntryCompletionError("holdout labels exposed to model selection")
    if payload.get("calibration_labels_available_to_parameter_fitting") is not False:
        raise Stage1BEntryCompletionError("calibration labels exposed to fitting")
    if payload.get("augmentation_scope") != "TRAIN_ONLY":
        raise Stage1BEntryCompletionError("augmentation scope changed")
    if payload.get("training_authorized") is not False:
        raise Stage1BEntryCompletionError("payload stage must not authorize training")

    if model.get("model_implementation_complete") is not True:
        raise Stage1BEntryCompletionError("model implementation incomplete")
    if model.get("implementation_version") != MODEL_IMPLEMENTATION_VERSION:
        raise Stage1BEntryCompletionError("model implementation version changed")
    if model.get("model_seed") != MODEL_SEED:
        raise Stage1BEntryCompletionError("model seed changed")
    if model.get("score_semantics") != SCORE_SEMANTICS:
        raise Stage1BEntryCompletionError("model score semantics changed")
    if model.get("fit_partition") != "TRAIN" or model.get("evaluation_partition") != "VALIDATION":
        raise Stage1BEntryCompletionError("model partition policy changed")
    if model.get("variant_policy") != "EQUAL_MASS_SET_VALUED_TARGETS":
        raise Stage1BEntryCompletionError("variant policy changed")
    if model.get("untrusted_pickle_loading_allowed") is not False:
        raise Stage1BEntryCompletionError("pickle loading must remain forbidden")
    if model.get("calibrated_probability_output") is not False:
        raise Stage1BEntryCompletionError("uncalibrated model cannot claim probability output")
    if model.get("model_training_started") is not False or model.get("training_authorized") is not False:
        raise Stage1BEntryCompletionError("model implementation stage pre-authorized training")
    if model.get("production_authority") is not False:
        raise Stage1BEntryCompletionError("model implementation cannot grant production authority")

    if environment.get("python_version") != "3.12.8":
        raise Stage1BEntryCompletionError("Python version lock changed")
    if environment.get("dependencies") != [] or environment.get("stdlib_only") is not True:
        raise Stage1BEntryCompletionError("first model must remain dependency-free")
    if environment.get("implementation_version") != MODEL_IMPLEMENTATION_VERSION:
        raise Stage1BEntryCompletionError("environment/model implementation mismatch")
    if environment.get("model_seed") != MODEL_SEED:
        raise Stage1BEntryCompletionError("environment model seed mismatch")
    if environment.get("checkpoint_format") != "CANONICAL_JSON_ONLY":
        raise Stage1BEntryCompletionError("checkpoint format changed")
    if environment.get("pickle_loading_allowed") is not False:
        raise Stage1BEntryCompletionError("pickle loading must remain forbidden")

    return {
        "schema_version": ENTRY_COMPLETION_SCHEMA,
        "source_corpus": EXPECTED_SOURCE,
        "source_revision": PINNED_TAVERN_REVISION,
        "dataset_readiness_gate": "PASS",
        "leakage_gate": "PASS",
        "promotion_threshold_status": "FROZEN",
        "promotion_scope": "OFFLINE_SHADOW_ONLY",
        "score_input_realization_complete": True,
        "deterministic_feature_schema_complete": True,
        "training_payload_manifest_complete": True,
        "model_implementation_complete": True,
        "remaining_blockers": [],
        "entry_gate_status": "PASS",
        "training_scope": "OFFLINE_EXPERIMENT_ONLY",
        "training_authorized": True,
        "model_training_started": False,
        "calibration_access_during_training": False,
        "holdout_access_during_training": False,
        "holdout_access_during_model_selection": False,
        "production_authority": False,
    }


def canonical_stage1b_entry_completion_json(data: dict[str, object]) -> str:
    if data.get("schema_version") != ENTRY_COMPLETION_SCHEMA:
        raise Stage1BEntryCompletionError("unsupported Stage 1-B completion schema")
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
