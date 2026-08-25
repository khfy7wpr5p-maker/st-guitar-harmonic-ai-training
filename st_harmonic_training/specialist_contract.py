from __future__ import annotations

import json
from typing import Any

from .tavern_structure import PINNED_TAVERN_REVISION
from .training_payload import PINNED_NORMALIZED_TARGET_MANIFEST_SHA256

SPECIALIST_CONTRACT_SCHEMA = "st-guitar-harmony-specialist-contract-v1"
SOURCE_CORPUS = "TAVERN_REVIEWED_694"
NORMALIZED_TARGET_COUNT = 747

FIRST_WAVE_SPECIALISTS = (
    {
        "specialist_id": "ROMAN_NUMERAL_SPECIALIST",
        "target_field": "roman_numeral",
        "supported_target_count": 747,
        "status": "DATASET_ENGINEERING_READY",
    },
    {
        "specialist_id": "KEY_SPECIALIST",
        "target_field": "key",
        "supported_target_count": 692,
        "status": "DATASET_ENGINEERING_READY",
    },
    {
        "specialist_id": "FUNCTION_SPECIALIST",
        "target_field": "phrase",
        "supported_target_count": 739,
        "status": "DATASET_ENGINEERING_READY",
    },
)

DEFERRED_SPECIALISTS = (
    {
        "specialist_id": "LOCAL_KEY_SPECIALIST",
        "target_field": "local_key",
        "supported_target_count": 1,
        "reason": "INSUFFICIENT_CURRENT_TAVERN_TARGET_SUPPORT",
    },
    {
        "specialist_id": "BASS_SPECIALIST",
        "target_field": "bass",
        "supported_target_count": 0,
        "reason": "CURRENT_TAVERN_ADAPTER_MATERIALIZES_NULL",
    },
    {
        "specialist_id": "INVERSION_SPECIALIST",
        "target_field": "inversion",
        "supported_target_count": 0,
        "reason": "CURRENT_TAVERN_ADAPTER_MATERIALIZES_NULL",
    },
    {
        "specialist_id": "CHORD_FAMILY_SPECIALIST",
        "target_field": "chord_family",
        "supported_target_count": 0,
        "reason": "CURRENT_TAVERN_ADAPTER_MATERIALIZES_NULL",
    },
    {
        "specialist_id": "EXTENSION_SPECIALIST",
        "target_field": "extension",
        "supported_target_count": 0,
        "reason": "CURRENT_TAVERN_ADAPTER_MATERIALIZES_NULL",
    },
    {
        "specialist_id": "SUSPENSION_SPECIALIST",
        "target_field": "suspension",
        "supported_target_count": 0,
        "reason": "CURRENT_TAVERN_ADAPTER_MATERIALIZES_NULL",
    },
    {
        "specialist_id": "ALTERATION_SPECIALIST",
        "target_field": "alteration",
        "supported_target_count": 0,
        "reason": "CURRENT_TAVERN_ADAPTER_MATERIALIZES_NULL",
    },
    {
        "specialist_id": "CADENCE_SPECIALIST",
        "target_field": "cadence",
        "supported_target_count": 0,
        "reason": "CURRENT_TAVERN_ADAPTER_MATERIALIZES_NULL",
    },
)


class SpecialistContractError(ValueError):
    pass


def build_specialist_contract() -> dict[str, object]:
    return {
        "schema_version": SPECIALIST_CONTRACT_SCHEMA,
        "source_corpus": SOURCE_CORPUS,
        "source_revision": PINNED_TAVERN_REVISION,
        "normalized_target_manifest_sha256": PINNED_NORMALIZED_TARGET_MANIFEST_SHA256,
        "normalized_target_count": NORMALIZED_TARGET_COUNT,
        "first_wave_specialists": [dict(item) for item in FIRST_WAVE_SPECIALISTS],
        "deferred_specialists": [dict(item) for item in DEFERRED_SPECIALISTS],
        "development_policy": {
            "fit_partition": "TRAIN_ONLY",
            "grouped_internal_cv_required": True,
            "feature_label_blind_required": True,
            "original_validation_reuse_during_iteration": False,
        },
        "training_authorized": False,
        "calibration_access_authorized": False,
        "holdout_access_authorized": False,
        "event_level_training_authorized": False,
        "production_authority": False,
        "deterministic_resolver_remains_authoritative": True,
    }


def validate_specialist_contract(data: object) -> dict[str, Any]:
    expected = build_specialist_contract()
    if not isinstance(data, dict):
        raise SpecialistContractError("specialist contract must be an object")
    if data != expected:
        raise SpecialistContractError("specialist contract differs from frozen Stage 2-A contract")
    return data


def canonical_specialist_contract_json(data: dict[str, object]) -> str:
    validate_specialist_contract(data)
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
