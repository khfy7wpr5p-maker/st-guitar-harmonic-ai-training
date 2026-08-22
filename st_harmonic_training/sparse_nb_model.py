from __future__ import annotations

from collections import defaultdict
import json
import math
from typing import Any

from .normalization import NORMALIZED_FIELDS

MODEL_SCHEMA = "st-guitar-harmony-fieldwise-sparse-nb-v1"
MODEL_IMPLEMENTATION_VERSION = "fieldwise-multinomial-nb-v1"
MODEL_SEED = 0
DEFAULT_ALPHA = 1.0
SCORE_SEMANTICS = "MODEL_SCORE_NOT_PROBABILITY"
ALLOWED_FIT_PARTITION = "TRAIN"
ALLOWED_EVAL_PARTITION = "VALIDATION"
MAX_FEATURE_KEYS = 8192
MAX_FEATURE_COUNT = 1_000_000
MAX_EXAMPLES = 100_000


class SparseNBModelError(ValueError):
    pass


def _class_key(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _validate_features(features: object) -> dict[str, int]:
    if not isinstance(features, dict) or len(features) > MAX_FEATURE_KEYS:
        raise SparseNBModelError("features must be a bounded object")
    result: dict[str, int] = {}
    total = 0
    for key, value in features.items():
        if not isinstance(key, str) or not key:
            raise SparseNBModelError("feature keys must be non-empty strings")
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise SparseNBModelError("feature values must be non-negative integers")
        if value:
            result[key] = value
            total += value
    if total > MAX_FEATURE_COUNT:
        raise SparseNBModelError("feature occurrence count exceeds bound")
    if not result:
        raise SparseNBModelError("feature vector must not be empty")
    return result


def _validate_label(label: object) -> dict[str, object]:
    if not isinstance(label, dict) or set(label) != set(NORMALIZED_FIELDS):
        raise SparseNBModelError("normalized label fields mismatch")
    return {field: label[field] for field in NORMALIZED_FIELDS}


def _validate_fit_examples(examples: object) -> list[dict[str, Any]]:
    if not isinstance(examples, list) or not examples or len(examples) > MAX_EXAMPLES:
        raise SparseNBModelError("fit examples must be a bounded non-empty array")
    seen: set[str] = set()
    validated: list[dict[str, Any]] = []
    for item in examples:
        if not isinstance(item, dict):
            raise SparseNBModelError("fit example must be an object")
        phrase = item.get("phrase_key")
        if not isinstance(phrase, str) or not phrase or phrase in seen:
            raise SparseNBModelError("fit phrase keys must be unique non-empty strings")
        seen.add(phrase)
        if item.get("partition") != ALLOWED_FIT_PARTITION:
            raise SparseNBModelError("fit may access TRAIN labels only")
        targets = item.get("targets")
        if not isinstance(targets, list) or len(targets) not in {1, 2}:
            raise SparseNBModelError("fit target set must contain one or two labels")
        labels = [_validate_label(target) for target in targets]
        if len({_class_key(label) for label in labels}) != len(labels):
            raise SparseNBModelError("duplicate acceptable targets are forbidden")
        validated.append(
            {
                "phrase_key": phrase,
                "partition": ALLOWED_FIT_PARTITION,
                "features": _validate_features(item.get("features")),
                "targets": labels,
            }
        )
    return validated


def fit_fieldwise_sparse_nb(
    examples: object,
    *,
    alpha: float = DEFAULT_ALPHA,
) -> dict[str, object]:
    if not isinstance(alpha, (int, float)) or isinstance(alpha, bool) or not math.isfinite(alpha) or alpha <= 0:
        raise SparseNBModelError("alpha must be a finite positive number")
    rows = _validate_fit_examples(examples)
    vocabulary = sorted({key for row in rows for key in row["features"]})
    if not vocabulary:
        raise SparseNBModelError("training vocabulary is empty")

    field_class_weights: dict[str, dict[str, float]] = {
        field: defaultdict(float) for field in NORMALIZED_FIELDS
    }
    field_token_totals: dict[str, dict[str, float]] = {
        field: defaultdict(float) for field in NORMALIZED_FIELDS
    }
    field_feature_counts: dict[str, dict[str, dict[str, float]]] = {
        field: defaultdict(lambda: defaultdict(float)) for field in NORMALIZED_FIELDS
    }

    variant_example_count = 0
    for row in rows:
        targets = row["targets"]
        if len(targets) == 2:
            variant_example_count += 1
        target_weight = 1.0 / len(targets)
        features = row["features"]
        for target in targets:
            for field in NORMALIZED_FIELDS:
                class_key = _class_key(target[field])
                field_class_weights[field][class_key] += target_weight
                for feature_key, count in features.items():
                    weighted = target_weight * count
                    field_feature_counts[field][class_key][feature_key] += weighted
                    field_token_totals[field][class_key] += weighted

    fields: dict[str, object] = {}
    for field in NORMALIZED_FIELDS:
        classes: list[dict[str, object]] = []
        for class_key in sorted(field_class_weights[field]):
            feature_counts = field_feature_counts[field][class_key]
            classes.append(
                {
                    "class_value": json.loads(class_key),
                    "class_key": class_key,
                    "class_weight": field_class_weights[field][class_key],
                    "token_total": field_token_totals[field][class_key],
                    "feature_counts": {
                        key: feature_counts[key] for key in sorted(feature_counts)
                    },
                }
            )
        fields[field] = {"classes": classes}

    return {
        "schema_version": MODEL_SCHEMA,
        "implementation_version": MODEL_IMPLEMENTATION_VERSION,
        "algorithm": "FIELDWISE_MULTINOMIAL_NAIVE_BAYES",
        "model_seed": MODEL_SEED,
        "alpha": float(alpha),
        "score_semantics": SCORE_SEMANTICS,
        "fit_partition": ALLOWED_FIT_PARTITION,
        "evaluation_partition": ALLOWED_EVAL_PARTITION,
        "training_example_count": len(rows),
        "variant_training_example_count": variant_example_count,
        "vocabulary": vocabulary,
        "fields": fields,
        "checkpoint_format": "CANONICAL_JSON_ONLY",
        "untrusted_pickle_loading_allowed": False,
        "calibrated_probability_output": False,
        "production_authority": False,
    }


def _validate_model(model: object) -> dict[str, Any]:
    if not isinstance(model, dict) or model.get("schema_version") != MODEL_SCHEMA:
        raise SparseNBModelError("unsupported model schema")
    if model.get("implementation_version") != MODEL_IMPLEMENTATION_VERSION:
        raise SparseNBModelError("model implementation version mismatch")
    if model.get("model_seed") != MODEL_SEED:
        raise SparseNBModelError("model seed mismatch")
    if model.get("score_semantics") != SCORE_SEMANTICS:
        raise SparseNBModelError("model score semantics changed")
    if model.get("checkpoint_format") != "CANONICAL_JSON_ONLY":
        raise SparseNBModelError("checkpoint format must remain canonical JSON")
    if model.get("untrusted_pickle_loading_allowed") is not False:
        raise SparseNBModelError("pickle loading must remain forbidden")
    if model.get("calibrated_probability_output") is not False:
        raise SparseNBModelError("uncalibrated model cannot claim probability output")
    vocabulary = model.get("vocabulary")
    if not isinstance(vocabulary, list) or not vocabulary or vocabulary != sorted(set(vocabulary)):
        raise SparseNBModelError("model vocabulary malformed")
    fields = model.get("fields")
    if not isinstance(fields, dict) or set(fields) != set(NORMALIZED_FIELDS):
        raise SparseNBModelError("model fields malformed")
    return model


def predict_fieldwise_sparse_nb(model: object, features: object) -> dict[str, object]:
    fitted = _validate_model(model)
    vector = _validate_features(features)
    vocabulary = set(fitted["vocabulary"])
    alpha = float(fitted["alpha"])
    vocabulary_size = len(vocabulary)
    prediction: dict[str, object] = {}
    field_scores: dict[str, dict[str, object]] = {}

    for field in NORMALIZED_FIELDS:
        classes = fitted["fields"][field]["classes"]
        total_class_weight = sum(float(item["class_weight"]) for item in classes)
        if total_class_weight <= 0:
            raise SparseNBModelError("model class weights malformed")
        best: tuple[float, str, object] | None = None
        for item in classes:
            class_key = str(item["class_key"])
            class_weight = float(item["class_weight"])
            token_total = float(item["token_total"])
            counts = item["feature_counts"]
            score = math.log(class_weight / total_class_weight)
            denominator = token_total + alpha * vocabulary_size
            for key, count in vector.items():
                if key not in vocabulary:
                    continue
                score += count * math.log((float(counts.get(key, 0.0)) + alpha) / denominator)
            candidate = (score, class_key, item["class_value"])
            if best is None or (candidate[0], candidate[1]) > (best[0], best[1]):
                best = candidate
        if best is None:
            raise SparseNBModelError("field has no classes")
        prediction[field] = best[2]
        field_scores[field] = {
            "value": best[2],
            "model_score": best[0],
            "score_semantics": SCORE_SEMANTICS,
        }

    return {
        "normalized_st_label": prediction,
        "field_scores": field_scores,
        "score_semantics": SCORE_SEMANTICS,
        "calibrated_probability": None,
        "authoritative_decision": False,
    }


def canonical_model_json(model: dict[str, object]) -> str:
    _validate_model(model)
    return json.dumps(model, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
