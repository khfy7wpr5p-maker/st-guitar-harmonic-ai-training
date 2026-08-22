from __future__ import annotations

import json
from typing import Any

from .normalization import NORMALIZATION_VERSION
from .tavern_readiness_audit import READINESS_SCHEMA
from .tavern_reviewed_split import EXPECTED_RECORD_DISTRIBUTION, EXPECTED_SEED
from .tavern_structure import PINNED_TAVERN_REVISION

TRAINING_CONTRACT_SCHEMA = "st-guitar-harmony-training-contract-v1"
SOURCE_SUBSET = "TAVERN_REVIEWED_694"
PYTHON_VERSION = "3.12.8"
EXPECTED_GOLD_COUNTS = {"GOLD_EXPERT": 641, "GOLD_VARIANT": 53}


class TrainingContractError(ValueError):
    pass


def build_stage1a_training_contract(readiness_audit: object) -> dict[str, object]:
    if not isinstance(readiness_audit, dict) or readiness_audit.get("schema_version") != READINESS_SCHEMA:
        raise TrainingContractError("unsupported Stage 0-U readiness schema")
    if readiness_audit.get("source_corpus") != SOURCE_SUBSET:
        raise TrainingContractError("training source subset mismatch")
    if readiness_audit.get("source_revision") != PINNED_TAVERN_REVISION:
        raise TrainingContractError("training source revision mismatch")
    if readiness_audit.get("eligible_record_count") != 694:
        raise TrainingContractError("eligible record count mismatch")
    if readiness_audit.get("gold_tier_counts") != EXPECTED_GOLD_COUNTS:
        raise TrainingContractError("gold tier distribution mismatch")
    if readiness_audit.get("split_seed") != EXPECTED_SEED:
        raise TrainingContractError("split seed mismatch")
    if readiness_audit.get("split_distribution") != EXPECTED_RECORD_DISTRIBUTION:
        raise TrainingContractError("split distribution mismatch")
    if readiness_audit.get("leakage_gate") != "PASS":
        raise TrainingContractError("leakage gate must pass before defining the training path")
    if readiness_audit.get("cross_corpus_lineage_bound") is not True:
        raise TrainingContractError("cross-corpus lineage must be bound")
    if readiness_audit.get("teacher_gold_present_in_calibration") is not True:
        raise TrainingContractError("calibration must contain teacher-gold metadata")
    if readiness_audit.get("teacher_gold_present_in_holdout") is not True:
        raise TrainingContractError("holdout must contain teacher-gold metadata")

    gate_status = readiness_audit.get("gate_status")
    blockers = readiness_audit.get("blockers")
    if gate_status not in {"PASS", "HOLD"} or not isinstance(blockers, list) or not all(isinstance(x, str) for x in blockers):
        raise TrainingContractError("malformed readiness gate status/blockers")
    readiness_training_authorized = readiness_audit.get("training_authorized")
    if readiness_training_authorized is not (gate_status == "PASS"):
        raise TrainingContractError("readiness training authority disagrees with gate status")

    start_blockers = list(blockers)
    start_blockers.append("PROMOTION_THRESHOLDS_PENDING_BASELINE")

    contract: dict[str, object] = {
        "schema_version": TRAINING_CONTRACT_SCHEMA,
        "contract_status": "FROZEN_PRETRAINING_CONTRACT",
        "source": {
            "subset_corpus": SOURCE_SUBSET,
            "source_revision": PINNED_TAVERN_REVISION,
            "eligible_record_count": 694,
            "gold_tier_counts": EXPECTED_GOLD_COUNTS,
            "normalization_version": NORMALIZATION_VERSION,
        },
        "model_role": {
            "purpose": "BOUNDED_ADVISORY_HARMONIC_ANALYSIS_EVIDENCE",
            "authoritative_harmony_decision": False,
            "direct_engine_state_mutation": False,
            "engine_integration_policy": "MODEL_OUTPUT_TO_VALIDATION_TO_DETERMINISTIC_POLICY_TO_EXPLAINABLE_EVIDENCE",
        },
        "input_contract": {
            "representation": "PINNED_SYMBOLIC_SCORE_PHRASE",
            "source_score_hash_verification_required": True,
            "safe_parser_required": True,
            "untrusted_dynamic_code_execution": False,
        },
        "target_contract": {
            "representation": "ST_NORMALIZED_HARMONIC_LABEL",
            "raw_selected_label_hash_verification_required": True,
            "normalization_version": NORMALIZATION_VERSION,
            "musical_inference_during_normalization": False,
            "variant_target_policy": "SET_VALUED_ACCEPT_ANY_HUMAN_VALID_TARGET",
            "arbitrary_variant_collapse_allowed": False,
        },
        "partition_contract": {
            "split_seed": EXPECTED_SEED,
            "record_distribution": EXPECTED_RECORD_DISTRIBUTION,
            "train_usage": "PARAMETER_FITTING_ONLY",
            "validation_usage": "EARLY_STOPPING_AND_MODEL_SELECTION_ONLY",
            "calibration_usage": "POST_SELECTION_CONFIDENCE_CALIBRATION_ONLY",
            "holdout_usage": "FINAL_EVALUATION_ONLY_AFTER_SELECTION_AND_CALIBRATION_POLICY_FREEZE",
            "holdout_access_during_training": False,
            "holdout_access_during_model_selection": False,
            "augmentation_scope": "TRAIN_ONLY",
            "cross_corpus_alias_partition_inheritance_required": True,
        },
        "evaluation_contract": {
            "metrics": [
                "EXACT_NORMALIZED_LABEL_MATCH",
                "VARIANT_AWARE_ACCEPTABLE_SET_ACCURACY",
                "ROMAN_NUMERAL_COMPONENT_ACCURACY",
                "FUNCTIONAL_COMPONENT_ACCURACY",
            ],
            "baseline_type": "DETERMINISTIC_NON_NEURAL_OR_RULE_BASELINE",
            "baseline_status": "PENDING_NORMALIZED_LABEL_MATERIALIZATION",
            "promotion_threshold_status": "PENDING_BASELINE",
            "holdout_for_threshold_tuning": False,
        },
        "confidence_contract": {
            "raw_model_score_name": "MODEL_SCORE",
            "raw_model_score_is_probability": False,
            "calibrated_confidence_requires_calibration_partition": True,
            "probability_wording_for_uncalibrated_score_forbidden": True,
        },
        "reproducibility_contract": {
            "python_version": PYTHON_VERSION,
            "model_random_seed": 0,
            "deterministic_algorithms_required": True,
            "dependency_lock_required": True,
            "split_seed": EXPECTED_SEED,
        },
        "artifact_security_contract": {
            "checkpoints_in_git_forbidden": True,
            "large_training_artifacts_in_git_forbidden": True,
            "untrusted_pickle_loading_forbidden": True,
            "training_input_read_only": True,
            "network_access_during_training_required": False,
            "raw_corpus_executable_content_forbidden": True,
        },
        "training_start_guard": {
            "stage0u_gate_status": gate_status,
            "raw_label_realization_complete": readiness_audit.get("raw_label_realization_complete") is True,
            "normalization_complete": readiness_audit.get("normalization_complete") is True,
            "promotion_thresholds_fixed": False,
            "blockers": start_blockers,
            "pass": False,
        },
        "model_training_started": False,
        "training_authorized": False,
    }
    validate_stage1a_training_contract(contract)
    return contract


def validate_stage1a_training_contract(contract: object) -> None:
    if not isinstance(contract, dict) or contract.get("schema_version") != TRAINING_CONTRACT_SCHEMA:
        raise TrainingContractError("unsupported training contract schema")
    if contract.get("contract_status") != "FROZEN_PRETRAINING_CONTRACT":
        raise TrainingContractError("training contract status is not frozen")
    source = contract.get("source")
    if not isinstance(source, dict) or source.get("subset_corpus") != SOURCE_SUBSET:
        raise TrainingContractError("source subset mismatch")
    if source.get("normalization_version") != NORMALIZATION_VERSION:
        raise TrainingContractError("normalization contract mismatch")

    role = contract.get("model_role")
    if not isinstance(role, dict) or role.get("authoritative_harmony_decision") is not False or role.get("direct_engine_state_mutation") is not False:
        raise TrainingContractError("model authority boundary violated")

    target = contract.get("target_contract")
    if not isinstance(target, dict):
        raise TrainingContractError("target contract missing")
    if target.get("raw_selected_label_hash_verification_required") is not True:
        raise TrainingContractError("raw target hash verification is mandatory")
    if target.get("musical_inference_during_normalization") is not False:
        raise TrainingContractError("normalization may not infer musical semantics")
    if target.get("variant_target_policy") != "SET_VALUED_ACCEPT_ANY_HUMAN_VALID_TARGET" or target.get("arbitrary_variant_collapse_allowed") is not False:
        raise TrainingContractError("GOLD_VARIANT handling must preserve the acceptable target set")

    partition = contract.get("partition_contract")
    if not isinstance(partition, dict) or partition.get("split_seed") != EXPECTED_SEED:
        raise TrainingContractError("partition split seed mismatch")
    if partition.get("record_distribution") != EXPECTED_RECORD_DISTRIBUTION:
        raise TrainingContractError("partition distribution mismatch")
    if partition.get("holdout_access_during_training") is not False or partition.get("holdout_access_during_model_selection") is not False:
        raise TrainingContractError("holdout leakage policy violated")
    if partition.get("augmentation_scope") != "TRAIN_ONLY":
        raise TrainingContractError("augmentation must be TRAIN_ONLY")

    evaluation = contract.get("evaluation_contract")
    if not isinstance(evaluation, dict) or evaluation.get("holdout_for_threshold_tuning") is not False:
        raise TrainingContractError("holdout cannot tune thresholds")
    if evaluation.get("promotion_threshold_status") != "PENDING_BASELINE":
        raise TrainingContractError("Stage 1-A promotion thresholds must remain pending baseline")

    confidence = contract.get("confidence_contract")
    if not isinstance(confidence, dict) or confidence.get("raw_model_score_is_probability") is not False:
        raise TrainingContractError("uncalibrated model score cannot be a probability")
    if confidence.get("probability_wording_for_uncalibrated_score_forbidden") is not True:
        raise TrainingContractError("uncalibrated probability wording must be forbidden")

    security = contract.get("artifact_security_contract")
    if not isinstance(security, dict):
        raise TrainingContractError("artifact security contract missing")
    for required_false_violation, message in (
        (security.get("checkpoints_in_git_forbidden") is not True, "checkpoints must be forbidden in Git"),
        (security.get("large_training_artifacts_in_git_forbidden") is not True, "large artifacts must be forbidden in Git"),
        (security.get("untrusted_pickle_loading_forbidden") is not True, "untrusted pickle loading must be forbidden"),
        (security.get("training_input_read_only") is not True, "training input must be read-only"),
    ):
        if required_false_violation:
            raise TrainingContractError(message)

    guard = contract.get("training_start_guard")
    if not isinstance(guard, dict) or guard.get("pass") is not False:
        raise TrainingContractError("Stage 1-A start guard must remain closed")
    blockers = guard.get("blockers")
    if not isinstance(blockers, list) or "PROMOTION_THRESHOLDS_PENDING_BASELINE" not in blockers:
        raise TrainingContractError("baseline/promotion threshold blocker must remain explicit")
    if contract.get("model_training_started") is not False or contract.get("training_authorized") is not False:
        raise TrainingContractError("Stage 1-A must not start or authorize model training")


def canonical_training_contract_json(contract: dict[str, object]) -> str:
    validate_stage1a_training_contract(contract)
    return json.dumps(contract, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
