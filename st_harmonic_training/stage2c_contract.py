from __future__ import annotations

import json
from typing import Any

from .stage1e_internal_cv import FOLD_COUNT, PINNED_GROUP_PLAN_SHA256
from .stage2b_specialist_materialization import (
    MATERIALIZATION_SCHEMA as STAGE2B_SCHEMA,
    SOURCE_CORPUS,
)
from .tavern_gold_materialization import PINNED_VALIDATED_SHA256
from .tavern_raw_label_realization import PINNED_TAVERN_ARCHIVE_SHA256
from .tavern_structure import PINNED_TAVERN_REVISION

CONTRACT_SCHEMA = "st-stage2c-specialist-grouped-cv-contract-v1"
PINNED_STAGE2B_PRIVATE_RECORD_MANIFEST_SHA256 = (
    "cd39690a4be0355a3fbbac303395d4888a89d4204a81af11598e21a822c040cd"
)
PINNED_STAGE2B_RECORD_COUNT = 487
PINNED_STAGE2B_WORK_FAMILY_COUNT = 18
PINNED_STAGE2B_SOURCE_TARGET_SLOT_COUNT = 500
PINNED_STAGE2B_FEATURE_VOCABULARY_COUNT = 5265
PINNED_STAGE2B_FEATURE_OCCURRENCE_COUNT = 94065
CANDIDATE_ALPHAS = (0.25, 0.5, 1.0, 2.0, 4.0)
SPECIALIST_IDS = (
    "ROMAN_NUMERAL_SPECIALIST",
    "KEY_SPECIALIST",
    "FUNCTION_SPECIALIST",
)
MODEL_IMPLEMENTATION_VERSION = "specialist-multinomial-nb-v1"
SELECTION_METRIC = "GROUPED_CV_ACCEPTABLE_SET_ACCURACY"
SELECTION_POLICY = "MAX_POOLED_ACCURACY_THEN_LOWEST_ALPHA"


class Stage2CContractError(ValueError):
    pass


def build_stage2c_contract() -> dict[str, object]:
    return {
        "schema_version": CONTRACT_SCHEMA,
        "source_corpus": SOURCE_CORPUS,
        "source_revision": PINNED_TAVERN_REVISION,
        "source_stage2b_schema": STAGE2B_SCHEMA,
        "validated_human_decisions_sha256": PINNED_VALIDATED_SHA256,
        "archive_sha256": PINNED_TAVERN_ARCHIVE_SHA256,
        "stage2b_private_record_manifest_sha256": (
            PINNED_STAGE2B_PRIVATE_RECORD_MANIFEST_SHA256
        ),
        "record_count": PINNED_STAGE2B_RECORD_COUNT,
        "work_family_count": PINNED_STAGE2B_WORK_FAMILY_COUNT,
        "source_target_slot_count": PINNED_STAGE2B_SOURCE_TARGET_SLOT_COUNT,
        "feature_vocabulary_count": PINNED_STAGE2B_FEATURE_VOCABULARY_COUNT,
        "feature_occurrence_count": PINNED_STAGE2B_FEATURE_OCCURRENCE_COUNT,
        "group_plan_manifest_sha256": PINNED_GROUP_PLAN_SHA256,
        "fold_count": FOLD_COUNT,
        "specialists": list(SPECIALIST_IDS),
        "model_implementation_version": MODEL_IMPLEMENTATION_VERSION,
        "candidate_alphas": list(CANDIDATE_ALPHAS),
        "selection_metric": SELECTION_METRIC,
        "selection_policy": SELECTION_POLICY,
        "fit_scope": "STAGE0_T_TRAIN_INTERNAL_FOLDS_ONLY",
        "evaluation_scope": "STAGE0_T_TRAIN_HELD_OUT_INTERNAL_FOLD_ONLY",
        "development_model_fitting_authorized": True,
        "full_train_final_fit_authorized": False,
        "original_validation_target_access": False,
        "calibration_target_access": False,
        "holdout_target_access": False,
        "event_level_training_authorized": False,
        "production_authority": False,
        "calibrated_probability_output": False,
        "deterministic_resolver_remains_authoritative": True,
    }


def validate_stage2c_contract(data: object) -> dict[str, Any]:
    expected = build_stage2c_contract()
    if not isinstance(data, dict) or data != expected:
        raise Stage2CContractError("Stage 2-C contract differs from frozen contract")
    return data


def canonical_stage2c_contract_json(data: dict[str, object]) -> str:
    validate_stage2c_contract(data)
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
