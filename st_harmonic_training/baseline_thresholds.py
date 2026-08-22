from __future__ import annotations

from collections import Counter
import hashlib
import json
from typing import Any

from .normalization import NORMALIZED_FIELDS, NORMALIZATION_VERSION
from .tavern_readiness_completion import (
    COMPLETION_SCHEMA,
    PINNED_NORMALIZED_TARGET_MANIFEST_SHA256,
)
from .tavern_reviewed_split import EXPECTED_RECORD_DISTRIBUTION, EXPECTED_SEED
from .tavern_structure import PINNED_TAVERN_REVISION

BASELINE_SCHEMA = "st-guitar-harmony-majority-baseline-v1"
THRESHOLD_SCHEMA = "st-guitar-harmony-promotion-thresholds-v1"
EXPECTED_RECORD_COUNT = 694
EXPECTED_TRAIN_RECORD_COUNT = 487
EXPECTED_VALIDATION_RECORD_COUNT = 125
EXPECTED_TRAIN_TARGET_COUNT = 500
EXPECTED_VALIDATION_TARGET_COUNT = 154
EXPECTED_TRAIN_VARIANT_RECORD_COUNT = 13
EXPECTED_VALIDATION_VARIANT_RECORD_COUNT = 29
EXPECTED_UNIQUE_TRAIN_TARGET_COUNT = 435
EXPECTED_BASELINE_TRAIN_FREQUENCY = 13
PINNED_BASELINE_TARGET_SHA256 = "6bfc22d0bbc7d08e859ad2e6aa53a95fceb478322ad1e4585e4333c756aa7b5e"


class BaselineThresholdError(ValueError):
    pass


def _canonical_label(label: dict[str, object]) -> str:
    if set(label) != set(NORMALIZED_FIELDS):
        raise BaselineThresholdError("normalized label fields mismatch")
    return json.dumps(label, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _require_records(data: object, *, schema: str, label: str) -> list[dict[str, Any]]:
    if not isinstance(data, dict) or data.get("schema_version") != schema:
        raise BaselineThresholdError(f"unsupported {label} schema")
    records = data.get("records")
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        raise BaselineThresholdError(f"{label} records malformed")
    return records


def build_majority_target_baseline(
    normalized_targets: object,
    reviewed_split: object,
    *,
    expected_record_count: int = EXPECTED_RECORD_COUNT,
    expected_train_record_count: int = EXPECTED_TRAIN_RECORD_COUNT,
    expected_validation_record_count: int = EXPECTED_VALIDATION_RECORD_COUNT,
    expected_train_target_count: int = EXPECTED_TRAIN_TARGET_COUNT,
    expected_validation_target_count: int = EXPECTED_VALIDATION_TARGET_COUNT,
) -> dict[str, object]:
    from .tavern_normalization_adapter import NORMALIZED_TARGET_SCHEMA
    from .tavern_reviewed_split import SPLIT_SCHEMA

    target_records = _require_records(
        normalized_targets, schema=NORMALIZED_TARGET_SCHEMA, label="normalized target"
    )
    split_records = _require_records(
        reviewed_split, schema=SPLIT_SCHEMA, label="reviewed split"
    )

    for data, label in ((normalized_targets, "normalized target"), (reviewed_split, "reviewed split")):
        if data.get("source_corpus") != "TAVERN_REVIEWED_694":
            raise BaselineThresholdError(f"{label} source subset mismatch")
        if data.get("source_revision") != PINNED_TAVERN_REVISION:
            raise BaselineThresholdError(f"{label} source revision mismatch")
        if data.get("validated_human_decisions_sha256") is None:
            raise BaselineThresholdError(f"{label} missing human-decision digest")
        if data.get("training_authorized") is not False:
            raise BaselineThresholdError(f"{label} unexpectedly authorizes training")

    if normalized_targets.get("normalization_version") != NORMALIZATION_VERSION:
        raise BaselineThresholdError("normalization version mismatch")
    if normalized_targets.get("normalized_target_manifest_sha256") != PINNED_NORMALIZED_TARGET_MANIFEST_SHA256:
        raise BaselineThresholdError("normalized target manifest mismatch")
    if reviewed_split.get("seed") != EXPECTED_SEED:
        raise BaselineThresholdError("split seed mismatch")
    if reviewed_split.get("record_distribution") != EXPECTED_RECORD_DISTRIBUTION:
        raise BaselineThresholdError("split distribution mismatch")

    if len(target_records) != expected_record_count or len(split_records) != expected_record_count:
        raise BaselineThresholdError("record count mismatch")

    target_by_phrase: dict[str, dict[str, Any]] = {}
    for record in target_records:
        phrase = record.get("phrase_key")
        targets = record.get("targets")
        if not isinstance(phrase, str) or not phrase or phrase in target_by_phrase:
            raise BaselineThresholdError("duplicate or invalid target phrase key")
        if not isinstance(targets, list) or not targets:
            raise BaselineThresholdError("target set must be non-empty")
        for target in targets:
            if not isinstance(target, dict) or not isinstance(target.get("normalized_st_label"), dict):
                raise BaselineThresholdError("normalized target payload malformed")
            _canonical_label(target["normalized_st_label"])
        target_by_phrase[phrase] = record

    split_by_phrase: dict[str, str] = {}
    for record in split_records:
        phrase = record.get("phrase_key")
        partition = record.get("partition")
        if not isinstance(phrase, str) or not phrase or phrase in split_by_phrase:
            raise BaselineThresholdError("duplicate or invalid split phrase key")
        if partition not in {"TRAIN", "VALIDATION", "CALIBRATION", "HOLDOUT"}:
            raise BaselineThresholdError("unexpected split partition")
        split_by_phrase[phrase] = str(partition)

    if set(target_by_phrase) != set(split_by_phrase):
        raise BaselineThresholdError("target/split phrase sets differ")

    train_phrases = sorted(p for p, part in split_by_phrase.items() if part == "TRAIN")
    validation_phrases = sorted(p for p, part in split_by_phrase.items() if part == "VALIDATION")
    if len(train_phrases) != expected_train_record_count:
        raise BaselineThresholdError("TRAIN record count mismatch")
    if len(validation_phrases) != expected_validation_record_count:
        raise BaselineThresholdError("VALIDATION record count mismatch")

    frequency: Counter[str] = Counter()
    train_target_count = 0
    train_variant_record_count = 0
    for phrase in train_phrases:
        targets = target_by_phrase[phrase]["targets"]
        if len(targets) > 1:
            train_variant_record_count += 1
        for target in targets:
            frequency[_canonical_label(target["normalized_st_label"])] += 1
            train_target_count += 1
    if train_target_count != expected_train_target_count:
        raise BaselineThresholdError("TRAIN target count mismatch")
    if not frequency:
        raise BaselineThresholdError("TRAIN target frequency is empty")

    max_frequency = max(frequency.values())
    baseline_canonical = min(label for label, count in frequency.items() if count == max_frequency)
    baseline_label = json.loads(baseline_canonical)
    baseline_sha256 = hashlib.sha256(baseline_canonical.encode("utf-8")).hexdigest()

    exact = 0
    variant_aware = 0
    roman = 0
    functional = 0
    validation_target_count = 0
    validation_variant_record_count = 0
    for phrase in validation_phrases:
        targets = target_by_phrase[phrase]["targets"]
        if len(targets) > 1:
            validation_variant_record_count += 1
        validation_target_count += len(targets)
        labels = [target["normalized_st_label"] for target in targets]
        canonical_labels = {_canonical_label(label) for label in labels}
        if len(labels) == 1 and baseline_canonical in canonical_labels:
            exact += 1
        if baseline_canonical in canonical_labels:
            variant_aware += 1
        if any(label.get("roman_numeral") == baseline_label.get("roman_numeral") for label in labels):
            roman += 1
        if any(label.get("phrase") == baseline_label.get("phrase") for label in labels):
            functional += 1

    if validation_target_count != expected_validation_target_count:
        raise BaselineThresholdError("VALIDATION target count mismatch")

    denominator = len(validation_phrases)
    return {
        "schema_version": BASELINE_SCHEMA,
        "algorithm": "TRAIN_SELECTED_TARGET_MAJORITY_WITH_LEXICOGRAPHIC_TIE_BREAK",
        "source_corpus": "TAVERN_REVIEWED_694",
        "source_revision": PINNED_TAVERN_REVISION,
        "normalization_version": NORMALIZATION_VERSION,
        "normalized_target_manifest_sha256": PINNED_NORMALIZED_TARGET_MANIFEST_SHA256,
        "split_seed": EXPECTED_SEED,
        "fit_partition": "TRAIN",
        "evaluation_partition": "VALIDATION",
        "calibration_accessed": False,
        "holdout_accessed": False,
        "train_record_count": len(train_phrases),
        "train_target_count": train_target_count,
        "train_variant_record_count": train_variant_record_count,
        "unique_train_target_count": len(frequency),
        "baseline_train_frequency": max_frequency,
        "baseline_target_sha256": baseline_sha256,
        "validation_record_count": denominator,
        "validation_target_count": validation_target_count,
        "validation_variant_record_count": validation_variant_record_count,
        "metrics": {
            "EXACT_NORMALIZED_LABEL_MATCH": exact / denominator,
            "VARIANT_AWARE_ACCEPTABLE_SET_ACCURACY": variant_aware / denominator,
            "ROMAN_NUMERAL_COMPONENT_ACCURACY": roman / denominator,
            "FUNCTIONAL_COMPONENT_ACCURACY": functional / denominator,
        },
        "model_training_started": False,
        "training_authorized": False,
    }


def build_promotion_thresholds(dataset_readiness: object, baseline: object) -> dict[str, object]:
    if not isinstance(dataset_readiness, dict) or dataset_readiness.get("schema_version") != COMPLETION_SCHEMA:
        raise BaselineThresholdError("unsupported dataset readiness schema")
    if dataset_readiness.get("dataset_readiness_gate") != "PASS":
        raise BaselineThresholdError("dataset readiness must PASS")
    if dataset_readiness.get("training_payload_ready") is not True:
        raise BaselineThresholdError("training payload is not ready")
    if dataset_readiness.get("training_authorized") is not False:
        raise BaselineThresholdError("dataset readiness cannot pre-authorize training")
    if not isinstance(baseline, dict) or baseline.get("schema_version") != BASELINE_SCHEMA:
        raise BaselineThresholdError("unsupported baseline schema")
    if baseline.get("fit_partition") != "TRAIN" or baseline.get("evaluation_partition") != "VALIDATION":
        raise BaselineThresholdError("baseline partition policy mismatch")
    if baseline.get("calibration_accessed") is not False or baseline.get("holdout_accessed") is not False:
        raise BaselineThresholdError("baseline accessed forbidden partitions")
    if baseline.get("baseline_target_sha256") != PINNED_BASELINE_TARGET_SHA256:
        raise BaselineThresholdError("baseline target digest changed")
    if baseline.get("train_record_count") != EXPECTED_TRAIN_RECORD_COUNT:
        raise BaselineThresholdError("baseline TRAIN count changed")
    if baseline.get("validation_record_count") != EXPECTED_VALIDATION_RECORD_COUNT:
        raise BaselineThresholdError("baseline VALIDATION count changed")
    if baseline.get("train_target_count") != EXPECTED_TRAIN_TARGET_COUNT:
        raise BaselineThresholdError("baseline TRAIN target count changed")
    if baseline.get("validation_target_count") != EXPECTED_VALIDATION_TARGET_COUNT:
        raise BaselineThresholdError("baseline VALIDATION target count changed")
    if baseline.get("train_variant_record_count") != EXPECTED_TRAIN_VARIANT_RECORD_COUNT:
        raise BaselineThresholdError("baseline TRAIN variant count changed")
    if baseline.get("validation_variant_record_count") != EXPECTED_VALIDATION_VARIANT_RECORD_COUNT:
        raise BaselineThresholdError("baseline VALIDATION variant count changed")
    if baseline.get("unique_train_target_count") != EXPECTED_UNIQUE_TRAIN_TARGET_COUNT:
        raise BaselineThresholdError("unique TRAIN target count changed")
    if baseline.get("baseline_train_frequency") != EXPECTED_BASELINE_TRAIN_FREQUENCY:
        raise BaselineThresholdError("baseline frequency changed")

    metrics = baseline.get("metrics")
    expected_metrics = {
        "EXACT_NORMALIZED_LABEL_MATCH": 0.0,
        "VARIANT_AWARE_ACCEPTABLE_SET_ACCURACY": 0.0,
        "ROMAN_NUMERAL_COMPONENT_ACCURACY": 0.0,
        "FUNCTIONAL_COMPONENT_ACCURACY": 0.04,
    }
    if metrics != expected_metrics:
        raise BaselineThresholdError("real baseline metrics changed")

    thresholds = {
        "EXACT_NORMALIZED_LABEL_MATCH": 0.10,
        "VARIANT_AWARE_ACCEPTABLE_SET_ACCURACY": 0.10,
        "ROMAN_NUMERAL_COMPONENT_ACCURACY": 0.15,
        "FUNCTIONAL_COMPONENT_ACCURACY": 0.10,
    }
    return {
        "schema_version": THRESHOLD_SCHEMA,
        "source_corpus": "TAVERN_REVIEWED_694",
        "source_revision": PINNED_TAVERN_REVISION,
        "baseline_schema_version": BASELINE_SCHEMA,
        "baseline_target_sha256": PINNED_BASELINE_TARGET_SHA256,
        "baseline_metrics": expected_metrics,
        "promotion_scope": "OFFLINE_SHADOW_ONLY",
        "validation_thresholds": thresholds,
        "threshold_policy": "ABSOLUTE_FLOOR_ABOVE_TRIVIAL_TRAIN_MAJORITY_BASELINE",
        "requires_all_metrics": True,
        "requires_full_validation_coverage": True,
        "requires_zero_leakage_violations": True,
        "requires_deterministic_rerun_match": True,
        "holdout_for_threshold_tuning": False,
        "calibration_for_threshold_tuning": False,
        "production_promotion_authorized": False,
        "promotion_threshold_status": "FROZEN",
        "training_start_blocker_resolved": "PROMOTION_THRESHOLDS_PENDING_BASELINE",
        "model_training_started": False,
        "training_authorized": False,
    }


def canonical_json(data: dict[str, object], *, schema: str) -> str:
    if data.get("schema_version") != schema:
        raise BaselineThresholdError("unexpected schema")
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
