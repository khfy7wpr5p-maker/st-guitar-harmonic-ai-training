from __future__ import annotations

import json
from typing import Any

from .stage1e_internal_cv import PINNED_GROUP_PLAN_SHA256
from .stage2c_contract import PINNED_STAGE2B_PRIVATE_RECORD_MANIFEST_SHA256
from .tavern_event_alignment_audit import PINNED_ALIGNMENT_MANIFEST_SHA256

CONTRACT_SCHEMA = "st-stage2e-specialist-target-reformulation-contract-v1"
STAGE2D_RECEIPT_SCHEMA = "st-stage2d-private-learnability-receipt-v1"
SOURCE_CORPUS = "TAVERN_REVIEWED_694"


class Stage2ETargetReformulationError(ValueError):
    pass


STAGE2D_OBSERVED_METRICS: dict[str, dict[str, object]] = {
    "KEY_SPECIALIST": {
        "eligible_record_count": 461,
        "missing_record_count": 26,
        "unique_target_count": 12,
        "singleton_target_fraction": 0.083333333333,
        "target_reuse_factor": 38.416666666667,
        "pooled_unseen_target_occurrence_rate": 0.015184381779,
        "pooled_closed_set_oracle_ceiling": 0.984815618221,
        "sequence_length_mean": 1.0,
        "sequence_length_max": 1,
    },
    "FUNCTION_SPECIALIST": {
        "eligible_record_count": 478,
        "missing_record_count": 9,
        "unique_target_count": 101,
        "singleton_target_fraction": 0.564356435644,
        "target_reuse_factor": 4.772277227723,
        "pooled_unseen_target_occurrence_rate": 0.271784232365,
        "pooled_closed_set_oracle_ceiling": 0.734309623431,
        "sequence_length_mean": 4.910788381743,
        "sequence_length_max": 56,
    },
    "ROMAN_NUMERAL_SPECIALIST": {
        "eligible_record_count": 487,
        "missing_record_count": 0,
        "unique_target_count": 432,
        "singleton_target_fraction": 0.909722222222,
        "target_reuse_factor": 1.148148148148,
        "pooled_unseen_target_occurrence_rate": 1.0,
        "pooled_closed_set_oracle_ceiling": 0.0,
        "sequence_length_mean": 11.012096774194,
        "sequence_length_max": 65,
    },
}


def build_stage2d_private_receipt() -> dict[str, object]:
    return {
        "schema_version": STAGE2D_RECEIPT_SCHEMA,
        "receipt_basis": "OPERATOR_PROVIDED_SUMMARY_VALUES",
        "exact_summary_file_sha256_bound": False,
        "source_stage2b_private_record_manifest_sha256": (
            PINNED_STAGE2B_PRIVATE_RECORD_MANIFEST_SHA256
        ),
        "record_count": 487,
        "work_family_count": 18,
        "fold_count": 3,
        "group_plan_manifest_sha256": PINNED_GROUP_PLAN_SHA256,
        "audit_scope": "STAGE0_T_TRAIN_TARGETS_ONLY",
        "result_scope": "TRAIN_ONLY_TARGET_LEARNABILITY_DIAGNOSTIC",
        "specialists": STAGE2D_OBSERVED_METRICS,
        "target_values_serialized": False,
        "model_fitting_started": False,
        "model_selection_started": False,
        "full_train_final_fit_started": False,
        "original_validation_target_access": False,
        "calibration_target_access": False,
        "holdout_target_access": False,
        "event_level_training_authorized": False,
        "production_authority": False,
        "deterministic_resolver_remains_authoritative": True,
    }


def build_stage2e_contract() -> dict[str, object]:
    return {
        "schema_version": CONTRACT_SCHEMA,
        "source_corpus": SOURCE_CORPUS,
        "source_stage2b_private_record_manifest_sha256": (
            PINNED_STAGE2B_PRIVATE_RECORD_MANIFEST_SHA256
        ),
        "source_stage1d_alignment_manifest_sha256": PINNED_ALIGNMENT_MANIFEST_SHA256,
        "source_stage1e_group_plan_manifest_sha256": PINNED_GROUP_PLAN_SHA256,
        "source_stage2d_receipt_schema": STAGE2D_RECEIPT_SCHEMA,
        "decision_basis": "TRAIN_ONLY_TARGET_LEARNABILITY_DIAGNOSTIC",
        "specialists": {
            "KEY_SPECIALIST": {
                "current_target_field": "key",
                "current_target_shape": "SCALAR_CLASS",
                "stage2d_closed_set_oracle_ceiling": 0.984815618221,
                "stage2d_unseen_target_occurrence_rate": 0.015184381779,
                "target_decision": "PRESERVE_SCALAR_TARGET",
                "next_target_shape": "SCALAR_CLASS",
                "next_prerequisite": "SEPARATE_TRAIN_ONLY_MODEL_FEATURE_GATE_REQUIRED",
            },
            "FUNCTION_SPECIALIST": {
                "current_target_field": "phrase",
                "current_target_shape": "WHOLE_PHRASE_JSON_SEQUENCE_AS_CLASS",
                "stage2d_closed_set_oracle_ceiling": 0.734309623431,
                "stage2d_unseen_target_occurrence_rate": 0.271784232365,
                "target_decision": "RETIRE_WHOLE_PHRASE_CLASSIFICATION_TARGET",
                "next_target_shape": "ALIGNED_FUNCTION_EVENT_OR_TOKEN_SEQUENCE",
                "next_prerequisite": "FUNCTION_EVENT_CARRIER_ALIGNMENT_AUDIT_REQUIRED",
            },
            "ROMAN_NUMERAL_SPECIALIST": {
                "current_target_field": "roman_numeral",
                "current_target_shape": "WHOLE_PHRASE_JSON_SEQUENCE_AS_CLASS",
                "stage2d_closed_set_oracle_ceiling": 0.0,
                "stage2d_unseen_target_occurrence_rate": 1.0,
                "target_decision": "RETIRE_WHOLE_PHRASE_CLASSIFICATION_TARGET",
                "next_target_shape": "ALIGNED_HARMONIC_EVENT_SEQUENCE",
                "next_prerequisite": "STAGE1E_PRIVATE_TRAIN_EVENT_MATERIALIZATION_AND_STAGE1F_CONTRACT_REQUIRED",
            },
        },
        "function_alignment_scope": "NOT_YET_PROVEN",
        "roman_alignment_scope": "STAGE1D_CANDIDATES_ONLY_NOT_AUTHORITY",
        "stage1d_quarantine_reuse_authorized": False,
        "target_reformulation_only": True,
        "model_fitting_authorized": False,
        "model_selection_authorized": False,
        "full_train_final_fit_authorized": False,
        "event_target_materialization_authorized": False,
        "event_level_training_authorized": False,
        "original_validation_target_access": False,
        "calibration_target_access": False,
        "holdout_target_access": False,
        "production_authority": False,
        "calibrated_probability_output": False,
        "deterministic_resolver_remains_authoritative": True,
    }


def validate_stage2d_private_receipt(data: object) -> dict[str, Any]:
    expected = build_stage2d_private_receipt()
    if not isinstance(data, dict) or data != expected:
        raise Stage2ETargetReformulationError(
            "Stage 2-D private receipt differs from bounded observed receipt"
        )
    return data


def validate_stage2e_contract(data: object) -> dict[str, Any]:
    expected = build_stage2e_contract()
    if not isinstance(data, dict) or data != expected:
        raise Stage2ETargetReformulationError(
            "Stage 2-E contract differs from frozen reformulation contract"
        )
    return data


def canonical_stage2d_receipt_json(data: dict[str, object]) -> str:
    validate_stage2d_private_receipt(data)
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"


def canonical_stage2e_contract_json(data: dict[str, object]) -> str:
    validate_stage2e_contract(data)
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
