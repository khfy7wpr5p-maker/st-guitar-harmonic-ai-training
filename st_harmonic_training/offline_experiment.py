from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
import sys
from typing import Any

from .baseline_thresholds import EXPECTED_THRESHOLDS
from .normalization import NORMALIZED_FIELDS
from .sparse_nb_model import (
    MODEL_IMPLEMENTATION_VERSION,
    SCORE_SEMANTICS,
    canonical_model_json,
    fit_fieldwise_sparse_nb,
    predict_fieldwise_sparse_nb,
)
from .stage1b_entry_completion import ENTRY_COMPLETION_SCHEMA
from .tavern_kern_features import FEATURE_SCHEMA, PINNED_SCORE_INPUT_MANIFEST_SHA256
from .tavern_normalization_adapter import NORMALIZED_TARGET_SCHEMA
from .tavern_reviewed_split import EXPECTED_SEED, SPLIT_SCHEMA
from .tavern_structure import PINNED_TAVERN_REVISION
from .training_payload import (
    PINNED_FEATURE_MANIFEST_SHA256,
    PINNED_NORMALIZED_TARGET_MANIFEST_SHA256,
    PINNED_TRAINING_PAYLOAD_MANIFEST_SHA256,
)

SHARD_SCHEMA = "st-guitar-harmony-private-experiment-shard-v1"
EXPERIMENT_SCHEMA = "st-guitar-harmony-offline-experiment-v1"
LOCKED_PYTHON = (3, 12, 8)
SOURCE_CORPUS = "TAVERN_REVIEWED_694"
REAL_PARTITION_COUNTS = {"TRAIN": 487, "VALIDATION": 125}
REAL_TARGET_COUNTS = {"TRAIN": 500, "VALIDATION": 154}
ALLOWED_SHARD_PARTITIONS = frozenset(REAL_PARTITION_COUNTS)
SEALED_PARTITIONS = ("CALIBRATION", "HOLDOUT")


class OfflineExperimentError(ValueError):
    pass


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _index(records: object, label: str) -> dict[str, dict[str, Any]]:
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        raise OfflineExperimentError(f"{label} records malformed")
    result: dict[str, dict[str, Any]] = {}
    for item in records:
        phrase = item.get("phrase_key")
        if not isinstance(phrase, str) or not phrase or phrase in result:
            raise OfflineExperimentError(f"duplicate/invalid {label} phrase key")
        result[phrase] = item
    return result


def _validate_normalized_label(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != set(NORMALIZED_FIELDS):
        raise OfflineExperimentError("normalized target fields mismatch")
    for field in NORMALIZED_FIELDS:
        item = value[field]
        if item is not None and not isinstance(item, str):
            raise OfflineExperimentError("normalized target values must be text or null")
    return {field: value[field] for field in NORMALIZED_FIELDS}


def _validate_feature_vector(value: object) -> dict[str, int]:
    if not isinstance(value, dict) or not value:
        raise OfflineExperimentError("feature vector must be a non-empty object")
    result: dict[str, int] = {}
    for key, count in value.items():
        if not isinstance(key, str) or not key:
            raise OfflineExperimentError("feature key malformed")
        if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
            raise OfflineExperimentError("feature count must be a positive integer")
        result[key] = count
    return dict(sorted(result.items()))


def _require_entry_pass(entry: object) -> dict[str, Any]:
    if not isinstance(entry, dict) or entry.get("schema_version") != ENTRY_COMPLETION_SCHEMA:
        raise OfflineExperimentError("unsupported Stage 1-B entry evidence")
    if entry.get("source_corpus") != SOURCE_CORPUS:
        raise OfflineExperimentError("entry source subset mismatch")
    if entry.get("source_revision") != PINNED_TAVERN_REVISION:
        raise OfflineExperimentError("entry source revision mismatch")
    if entry.get("entry_gate_status") != "PASS":
        raise OfflineExperimentError("Stage 1-B entry gate must PASS")
    if entry.get("training_scope") != "OFFLINE_EXPERIMENT_ONLY":
        raise OfflineExperimentError("training scope must remain offline experiment only")
    if entry.get("training_authorized") is not True:
        raise OfflineExperimentError("offline training is not authorized")
    if entry.get("production_authority") is not False:
        raise OfflineExperimentError("production authority must remain disabled")
    if entry.get("calibration_access_during_training") is not False:
        raise OfflineExperimentError("CALIBRATION must remain sealed during training")
    if entry.get("holdout_access_during_training") is not False:
        raise OfflineExperimentError("HOLDOUT must remain sealed during training")
    if entry.get("holdout_access_during_model_selection") is not False:
        raise OfflineExperimentError("HOLDOUT must remain sealed during model selection")
    return entry


def build_private_experiment_shards(
    features: object,
    normalized_targets: object,
    reviewed_split: object,
    entry_completion: object,
    *,
    expected_partition_counts: dict[str, int] | None = None,
    expected_target_counts: dict[str, int] | None = None,
) -> dict[str, dict[str, object]]:
    """Create TRAIN/VALIDATION-only local shards; CALIBRATION/HOLDOUT are never serialized."""
    _require_entry_pass(entry_completion)
    if expected_partition_counts is None:
        expected_partition_counts = REAL_PARTITION_COUNTS
    if expected_target_counts is None:
        expected_target_counts = REAL_TARGET_COUNTS

    if not isinstance(features, dict) or features.get("schema_version") != FEATURE_SCHEMA:
        raise OfflineExperimentError("unsupported feature schema")
    if not isinstance(normalized_targets, dict) or normalized_targets.get("schema_version") != NORMALIZED_TARGET_SCHEMA:
        raise OfflineExperimentError("unsupported normalized-target schema")
    if not isinstance(reviewed_split, dict) or reviewed_split.get("schema_version") != SPLIT_SCHEMA:
        raise OfflineExperimentError("unsupported split schema")

    for data, label in (
        (features, "features"),
        (normalized_targets, "normalized targets"),
        (reviewed_split, "split"),
    ):
        if data.get("source_corpus") != SOURCE_CORPUS:
            raise OfflineExperimentError(f"{label} source subset mismatch")
        if data.get("source_revision") != PINNED_TAVERN_REVISION:
            raise OfflineExperimentError(f"{label} source revision mismatch")
        if data.get("training_authorized") is not False:
            raise OfflineExperimentError(f"{label} unexpectedly pre-authorizes training")

    if features.get("feature_manifest_sha256") != PINNED_FEATURE_MANIFEST_SHA256:
        raise OfflineExperimentError("feature manifest digest mismatch")
    if features.get("score_input_manifest_sha256") != PINNED_SCORE_INPUT_MANIFEST_SHA256:
        raise OfflineExperimentError("score input manifest digest mismatch")
    if normalized_targets.get("normalized_target_manifest_sha256") != PINNED_NORMALIZED_TARGET_MANIFEST_SHA256:
        raise OfflineExperimentError("normalized target manifest digest mismatch")
    if reviewed_split.get("seed") != EXPECTED_SEED:
        raise OfflineExperimentError("split seed mismatch")
    if reviewed_split.get("label_aware_seed_selection") is not False:
        raise OfflineExperimentError("split must remain label-blind")
    if reviewed_split.get("augmentation_scope") != "TRAIN_ONLY":
        raise OfflineExperimentError("augmentation scope changed")

    feature_by_phrase = _index(features.get("records"), "feature")
    target_by_phrase = _index(normalized_targets.get("records"), "target")
    split_by_phrase = _index(reviewed_split.get("records"), "split")
    if set(feature_by_phrase) != set(target_by_phrase) or set(feature_by_phrase) != set(split_by_phrase):
        raise OfflineExperimentError("feature/target/split phrase sets differ")

    records_by_partition: dict[str, list[dict[str, object]]] = {
        partition: [] for partition in ALLOWED_SHARD_PARTITIONS
    }
    target_counts: Counter[str] = Counter()
    split_groups: dict[str, set[str]] = {partition: set() for partition in ALLOWED_SHARD_PARTITIONS}

    for phrase in sorted(feature_by_phrase):
        split = split_by_phrase[phrase]
        partition = split.get("partition")
        if partition not in {"TRAIN", "VALIDATION", "CALIBRATION", "HOLDOUT"}:
            raise OfflineExperimentError(f"unexpected partition for {phrase}")
        if partition in SEALED_PARTITIONS:
            continue
        if partition not in ALLOWED_SHARD_PARTITIONS:
            raise OfflineExperimentError("unsupported experiment shard partition")

        feature = feature_by_phrase[phrase]
        target_record = target_by_phrase[phrase]
        targets = target_record.get("targets")
        if not isinstance(targets, list) or len(targets) not in {1, 2}:
            raise OfflineExperimentError(f"invalid target set for {phrase}")
        normalized_set: list[dict[str, object]] = []
        for target in targets:
            if not isinstance(target, dict):
                raise OfflineExperimentError(f"malformed target for {phrase}")
            normalized_set.append(_validate_normalized_label(target.get("normalized_st_label")))
        canonical_targets = {_canonical_bytes(target) for target in normalized_set}
        if len(canonical_targets) != len(normalized_set):
            raise OfflineExperimentError(f"duplicate acceptable target for {phrase}")

        split_group = split.get("split_group_id")
        if not isinstance(split_group, str) or not split_group:
            raise OfflineExperimentError(f"missing split group for {phrase}")
        split_groups[str(partition)].add(split_group)
        records_by_partition[str(partition)].append(
            {
                "phrase_key": phrase,
                "partition": partition,
                "split_group_id": split_group,
                "feature_sha256": feature.get("feature_sha256"),
                "features": _validate_feature_vector(feature.get("features")),
                "targets": normalized_set,
            }
        )
        target_counts[str(partition)] += len(normalized_set)

    if split_groups["TRAIN"] & split_groups["VALIDATION"]:
        raise OfflineExperimentError("TRAIN and VALIDATION share a split group")

    shards: dict[str, dict[str, object]] = {}
    for partition in sorted(ALLOWED_SHARD_PARTITIONS):
        records = records_by_partition[partition]
        if len(records) != expected_partition_counts[partition]:
            raise OfflineExperimentError(f"{partition} record count mismatch")
        if target_counts[partition] != expected_target_counts[partition]:
            raise OfflineExperimentError(f"{partition} target count mismatch")
        manifest_sha = hashlib.sha256(_canonical_bytes(records)).hexdigest()
        shards[partition] = {
            "schema_version": SHARD_SCHEMA,
            "source_corpus": SOURCE_CORPUS,
            "source_revision": PINNED_TAVERN_REVISION,
            "partition": partition,
            "split_seed": EXPECTED_SEED,
            "record_count": len(records),
            "target_count": target_counts[partition],
            "feature_manifest_sha256": PINNED_FEATURE_MANIFEST_SHA256,
            "normalized_target_manifest_sha256": PINNED_NORMALIZED_TARGET_MANIFEST_SHA256,
            "training_payload_manifest_sha256": PINNED_TRAINING_PAYLOAD_MANIFEST_SHA256,
            "sealed_partitions_not_serialized": list(SEALED_PARTITIONS),
            "parameter_fitting_allowed": partition == "TRAIN",
            "model_selection_evaluation_allowed": partition == "VALIDATION",
            "records": records,
            "shard_manifest_sha256": manifest_sha,
            "production_authority": False,
        }
    return shards


def _validate_shard(data: object, partition: str) -> dict[str, Any]:
    if partition not in ALLOWED_SHARD_PARTITIONS:
        raise OfflineExperimentError("unsupported shard partition")
    if not isinstance(data, dict) or data.get("schema_version") != SHARD_SCHEMA:
        raise OfflineExperimentError("unsupported experiment shard schema")
    if data.get("source_corpus") != SOURCE_CORPUS or data.get("source_revision") != PINNED_TAVERN_REVISION:
        raise OfflineExperimentError("experiment shard source identity mismatch")
    if data.get("partition") != partition:
        raise OfflineExperimentError("experiment shard partition mismatch")
    if data.get("split_seed") != EXPECTED_SEED:
        raise OfflineExperimentError("experiment shard split seed mismatch")
    if data.get("feature_manifest_sha256") != PINNED_FEATURE_MANIFEST_SHA256:
        raise OfflineExperimentError("experiment shard feature manifest mismatch")
    if data.get("normalized_target_manifest_sha256") != PINNED_NORMALIZED_TARGET_MANIFEST_SHA256:
        raise OfflineExperimentError("experiment shard target manifest mismatch")
    if data.get("training_payload_manifest_sha256") != PINNED_TRAINING_PAYLOAD_MANIFEST_SHA256:
        raise OfflineExperimentError("experiment shard payload manifest mismatch")
    if data.get("sealed_partitions_not_serialized") != list(SEALED_PARTITIONS):
        raise OfflineExperimentError("sealed partition declaration changed")
    records = data.get("records")
    indexed = _index(records, f"{partition} shard")
    if int(data.get("record_count", -1)) != len(indexed):
        raise OfflineExperimentError("experiment shard record count mismatch")
    manifest_sha = hashlib.sha256(_canonical_bytes(records)).hexdigest()
    if data.get("shard_manifest_sha256") != manifest_sha:
        raise OfflineExperimentError("experiment shard digest mismatch")
    expected_fit = partition == "TRAIN"
    expected_eval = partition == "VALIDATION"
    if data.get("parameter_fitting_allowed") is not expected_fit:
        raise OfflineExperimentError("experiment shard fitting authority mismatch")
    if data.get("model_selection_evaluation_allowed") is not expected_eval:
        raise OfflineExperimentError("experiment shard evaluation authority mismatch")
    if data.get("production_authority") is not False:
        raise OfflineExperimentError("experiment shard cannot grant production authority")
    return data


def require_locked_runtime() -> None:
    actual = tuple(sys.version_info[:3])
    if actual != LOCKED_PYTHON:
        raise OfflineExperimentError(
            f"official offline experiment requires Python {LOCKED_PYTHON}; got {actual}"
        )


def _record_to_fit_example(record: dict[str, Any]) -> dict[str, object]:
    if record.get("partition") != "TRAIN":
        raise OfflineExperimentError("fit example must come from TRAIN shard")
    return {
        "phrase_key": record["phrase_key"],
        "partition": "TRAIN",
        "features": record["features"],
        "targets": record["targets"],
    }


def _evaluate_validation(
    model: dict[str, object], validation_records: list[dict[str, Any]]
) -> dict[str, object]:
    exact = 0
    variant_aware = 0
    roman = 0
    functional = 0
    predictions: list[dict[str, object]] = []
    for record in validation_records:
        if record.get("partition") != "VALIDATION":
            raise OfflineExperimentError("evaluation may read VALIDATION only")
        targets = record.get("targets")
        if not isinstance(targets, list) or not targets:
            raise OfflineExperimentError("validation target set missing")
        prediction = predict_fieldwise_sparse_nb(model, record.get("features"))
        predicted_label = prediction["normalized_st_label"]
        if len(targets) == 1 and predicted_label == targets[0]:
            exact += 1
        if any(predicted_label == target for target in targets):
            variant_aware += 1
        if any(predicted_label.get("roman_numeral") == target.get("roman_numeral") for target in targets):
            roman += 1
        if any(predicted_label.get("phrase") == target.get("phrase") for target in targets):
            functional += 1
        predictions.append(
            {
                "phrase_key": record["phrase_key"],
                "prediction": predicted_label,
                "score_semantics": prediction["score_semantics"],
                "authoritative_decision": False,
            }
        )
    denominator = len(validation_records)
    if denominator == 0:
        raise OfflineExperimentError("validation shard is empty")
    metrics = {
        "EXACT_NORMALIZED_LABEL_MATCH": exact / denominator,
        "VARIANT_AWARE_ACCEPTABLE_SET_ACCURACY": variant_aware / denominator,
        "ROMAN_NUMERAL_COMPONENT_ACCURACY": roman / denominator,
        "FUNCTIONAL_COMPONENT_ACCURACY": functional / denominator,
    }
    return {"metrics": metrics, "predictions": predictions}


def run_offline_experiment(
    train_shard: object,
    validation_shard: object,
    entry_completion: object,
    *,
    enforce_runtime: bool = True,
) -> dict[str, object]:
    entry = _require_entry_pass(entry_completion)
    if enforce_runtime:
        require_locked_runtime()
    train = _validate_shard(train_shard, "TRAIN")
    validation = _validate_shard(validation_shard, "VALIDATION")

    train_groups = {str(item["split_group_id"]) for item in train["records"]}
    validation_groups = {str(item["split_group_id"]) for item in validation["records"]}
    if train_groups & validation_groups:
        raise OfflineExperimentError("TRAIN/VALIDATION split-group leakage detected")

    fit_examples = [_record_to_fit_example(item) for item in train["records"]]
    model_first = fit_fieldwise_sparse_nb(fit_examples)
    model_second = fit_fieldwise_sparse_nb(list(reversed(fit_examples)))
    first_bytes = canonical_model_json(model_first).encode("utf-8")
    second_bytes = canonical_model_json(model_second).encode("utf-8")
    if first_bytes != second_bytes:
        raise OfflineExperimentError("deterministic rerun mismatch")
    checkpoint_sha = hashlib.sha256(first_bytes).hexdigest()

    evaluation = _evaluate_validation(model_first, validation["records"])
    metrics = evaluation["metrics"]
    threshold_pass = {
        metric: bool(math.isfinite(float(metrics[metric])) and float(metrics[metric]) >= threshold)
        for metric, threshold in EXPECTED_THRESHOLDS.items()
    }
    all_thresholds_pass = all(threshold_pass.values())
    prediction_manifest_sha = hashlib.sha256(
        _canonical_bytes(evaluation["predictions"])
    ).hexdigest()

    return {
        "schema_version": EXPERIMENT_SCHEMA,
        "source_corpus": SOURCE_CORPUS,
        "source_revision": PINNED_TAVERN_REVISION,
        "entry_gate_status": entry["entry_gate_status"],
        "training_scope": "OFFLINE_EXPERIMENT_ONLY",
        "implementation_version": MODEL_IMPLEMENTATION_VERSION,
        "python_version_required": ".".join(str(x) for x in LOCKED_PYTHON),
        "fit_partition": "TRAIN",
        "evaluation_partition": "VALIDATION",
        "calibration_accessed": False,
        "holdout_accessed": False,
        "train_record_count": train["record_count"],
        "validation_record_count": validation["record_count"],
        "model_checkpoint_sha256": checkpoint_sha,
        "deterministic_rerun_match": True,
        "validation_prediction_manifest_sha256": prediction_manifest_sha,
        "validation_metrics": metrics,
        "frozen_validation_thresholds": EXPECTED_THRESHOLDS,
        "threshold_pass": threshold_pass,
        "all_thresholds_pass": all_thresholds_pass,
        "validation_gate_status": "PASS" if all_thresholds_pass else "HOLD",
        "promotion_scope": "OFFLINE_SHADOW_ONLY",
        "model_score_semantics": SCORE_SEMANTICS,
        "calibrated_probability_output": False,
        "model_training_started": True,
        "production_authority": False,
        "model_checkpoint": model_first,
    }


def build_experiment_summary(result: object) -> dict[str, object]:
    if not isinstance(result, dict) or result.get("schema_version") != EXPERIMENT_SCHEMA:
        raise OfflineExperimentError("unsupported experiment result schema")
    if result.get("production_authority") is not False:
        raise OfflineExperimentError("experiment cannot grant production authority")
    if result.get("calibration_accessed") is not False or result.get("holdout_accessed") is not False:
        raise OfflineExperimentError("sealed partitions were accessed")
    summary = {key: value for key, value in result.items() if key != "model_checkpoint"}
    summary["model_checkpoint_external_only"] = True
    return summary


def canonical_experiment_json(data: dict[str, object]) -> str:
    if data.get("schema_version") != EXPERIMENT_SCHEMA:
        raise OfflineExperimentError("unsupported experiment schema")
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
