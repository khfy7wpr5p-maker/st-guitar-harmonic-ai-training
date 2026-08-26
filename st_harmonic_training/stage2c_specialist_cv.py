from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import stat
from typing import Any

from .safe_ingest import load_bounded_json
from .stage1e_internal_cv import FOLD_COUNT, PINNED_GROUP_PLAN_SHA256
from .stage2b_specialist_materialization import (
    MATERIALIZATION_SCHEMA as STAGE2B_SCHEMA,
    SPECIALIST_FIELDS,
)
from .stage2c_contract import (
    CANDIDATE_ALPHAS,
    MODEL_IMPLEMENTATION_VERSION,
    PINNED_STAGE2B_FEATURE_OCCURRENCE_COUNT,
    PINNED_STAGE2B_FEATURE_VOCABULARY_COUNT,
    PINNED_STAGE2B_PRIVATE_RECORD_MANIFEST_SHA256,
    PINNED_STAGE2B_RECORD_COUNT,
    PINNED_STAGE2B_SOURCE_TARGET_SLOT_COUNT,
    PINNED_STAGE2B_WORK_FAMILY_COUNT,
    SELECTION_METRIC,
    SELECTION_POLICY,
    SPECIALIST_IDS,
    build_stage2c_contract,
    validate_stage2c_contract,
)
from .tavern_gold_materialization import PINNED_VALIDATED_SHA256
from .tavern_raw_label_realization import PINNED_TAVERN_ARCHIVE_SHA256
from .tavern_structure import PINNED_TAVERN_REVISION

SUMMARY_SCHEMA = "st-stage2c-specialist-grouped-cv-summary-v1"
SOURCE_CORPUS = "TAVERN_REVIEWED_694"
SCORE_SEMANTICS = "MODEL_SCORE_NOT_PROBABILITY"
MAX_PRIVATE_INPUT_BYTES = 64 * 1024 * 1024
MAX_FEATURE_KEYS = 8192
MAX_FEATURE_OCCURRENCES = 1_000_000
MAX_TARGETS_PER_RECORD = 2
EXPECTED_FOLD_RECORD_DISTRIBUTION = {"0": 156, "1": 167, "2": 164}
EXPECTED_FOLD_WORK_FAMILY_DISTRIBUTION = {"0": 6, "1": 6, "2": 6}
SPECIALIST_TARGET_FIELDS = dict(SPECIALIST_FIELDS)


class Stage2CSpecialistCVError(ValueError):
    pass


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _accuracy(correct: int, total: int) -> float:
    if total <= 0:
        raise Stage2CSpecialistCVError("accuracy denominator must be positive")
    return round(correct / total, 12)


def _validate_features(features: object) -> dict[str, int]:
    if not isinstance(features, dict) or not features or len(features) > MAX_FEATURE_KEYS:
        raise Stage2CSpecialistCVError("features must be a bounded non-empty object")
    result: dict[str, int] = {}
    total = 0
    for key, value in features.items():
        if not isinstance(key, str) or not key:
            raise Stage2CSpecialistCVError("feature keys must be non-empty strings")
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise Stage2CSpecialistCVError("feature counts must be non-negative integers")
        if value:
            result[key] = value
            total += value
    if not result or total > MAX_FEATURE_OCCURRENCES:
        raise Stage2CSpecialistCVError("feature vector is empty or exceeds occurrence bound")
    return dict(sorted(result.items()))


def _validate_specialist_payload(
    specialist_id: str,
    payload: object,
) -> tuple[str, ...]:
    if specialist_id not in SPECIALIST_IDS or not isinstance(payload, dict):
        raise Stage2CSpecialistCVError("specialist payload malformed")
    if payload.get("target_field") != SPECIALIST_TARGET_FIELDS[specialist_id]:
        raise Stage2CSpecialistCVError(
            f"specialist target field mismatch: {specialist_id}"
        )
    source_targets = payload.get("source_targets")
    effective_targets = payload.get("effective_targets")
    if not isinstance(source_targets, list) or len(source_targets) not in {1, 2}:
        raise Stage2CSpecialistCVError("specialist source targets malformed")
    if not isinstance(effective_targets, list) or len(effective_targets) > MAX_TARGETS_PER_RECORD:
        raise Stage2CSpecialistCVError("specialist effective targets malformed")

    seen_sources: set[str] = set()
    expected_effective: set[str] = set()
    for item in source_targets:
        if not isinstance(item, dict):
            raise Stage2CSpecialistCVError("specialist source target must be an object")
        source = item.get("source")
        value = item.get("value")
        if source not in {"A", "B"} or source in seen_sources:
            raise Stage2CSpecialistCVError("specialist source target source malformed")
        seen_sources.add(str(source))
        if value is not None and (not isinstance(value, str) or not value):
            raise Stage2CSpecialistCVError("specialist source target must be string/null")
        if isinstance(value, str):
            expected_effective.add(value)

    if not all(isinstance(value, str) and value for value in effective_targets):
        raise Stage2CSpecialistCVError("effective specialist targets must be strings")
    observed = tuple(effective_targets)
    if observed != tuple(sorted(set(observed))):
        raise Stage2CSpecialistCVError("effective specialist targets must be sorted unique")
    if set(observed) != expected_effective:
        raise Stage2CSpecialistCVError(
            "effective specialist targets differ from non-null source target set"
        )
    return observed


def validate_stage2b_private_payload(data: object) -> list[dict[str, Any]]:
    validate_stage2c_contract(build_stage2c_contract())
    if not isinstance(data, dict) or data.get("schema_version") != STAGE2B_SCHEMA:
        raise Stage2CSpecialistCVError("unsupported Stage 2-B private payload schema")
    expected_scalars = {
        "source_corpus": SOURCE_CORPUS,
        "source_revision": PINNED_TAVERN_REVISION,
        "validated_human_decisions_sha256": PINNED_VALIDATED_SHA256,
        "archive_sha256": PINNED_TAVERN_ARCHIVE_SHA256,
        "eligible_original_partition": "TRAIN",
        "record_count": PINNED_STAGE2B_RECORD_COUNT,
        "work_family_count": PINNED_STAGE2B_WORK_FAMILY_COUNT,
        "fold_count": FOLD_COUNT,
        "group_plan_manifest_sha256": PINNED_GROUP_PLAN_SHA256,
        "source_target_slot_count": PINNED_STAGE2B_SOURCE_TARGET_SLOT_COUNT,
        "feature_vocabulary_count": PINNED_STAGE2B_FEATURE_VOCABULARY_COUNT,
        "feature_occurrence_count": PINNED_STAGE2B_FEATURE_OCCURRENCE_COUNT,
        "private_record_manifest_sha256": PINNED_STAGE2B_PRIVATE_RECORD_MANIFEST_SHA256,
        "target_set_policy": "CANONICAL_NORMALIZED_UNIQUE_NON_NULL_SET",
        "annotation_parse_scope": "TRAIN_ONLY",
        "score_feature_scope": "TRAIN_ONLY",
    }
    for field, expected in expected_scalars.items():
        if data.get(field) != expected:
            raise Stage2CSpecialistCVError(f"Stage 2-B input pin mismatch: {field}")
    if data.get("fold_record_distribution") != EXPECTED_FOLD_RECORD_DISTRIBUTION:
        raise Stage2CSpecialistCVError("Stage 2-B fold record distribution changed")
    if data.get("fold_work_family_distribution") != EXPECTED_FOLD_WORK_FAMILY_DISTRIBUTION:
        raise Stage2CSpecialistCVError("Stage 2-B fold family distribution changed")
    for field in (
        "non_train_annotation_bodies_materialized",
        "original_validation_target_access",
        "calibration_target_access",
        "holdout_target_access",
        "event_level_training_authorized",
        "model_training_started",
        "training_authorized",
        "production_authority",
    ):
        if data.get(field) is not False:
            raise Stage2CSpecialistCVError(
                f"Stage 2-B access/authority boundary violated: {field}"
            )
    if data.get("deterministic_resolver_remains_authoritative") is not True:
        raise Stage2CSpecialistCVError("deterministic resolver authority changed")

    records = data.get("records")
    if not isinstance(records, list) or len(records) != PINNED_STAGE2B_RECORD_COUNT:
        raise Stage2CSpecialistCVError("Stage 2-B private records malformed")
    if _canonical_sha256(records) != PINNED_STAGE2B_PRIVATE_RECORD_MANIFEST_SHA256:
        raise Stage2CSpecialistCVError("Stage 2-B private record body digest mismatch")

    seen_phrases: set[str] = set()
    group_fold: dict[str, int] = {}
    fold_records: Counter[int] = Counter()
    fold_groups: dict[int, set[str]] = defaultdict(set)
    vocabulary: set[str] = set()
    feature_occurrences = 0
    validated: list[dict[str, Any]] = []
    for item in records:
        if not isinstance(item, dict):
            raise Stage2CSpecialistCVError("Stage 2-B private row must be an object")
        phrase = item.get("phrase_key")
        group = item.get("split_group_id")
        canonical = item.get("canonical_work_id")
        fold = item.get("development_fold")
        if not isinstance(phrase, str) or not phrase or phrase in seen_phrases:
            raise Stage2CSpecialistCVError("invalid/duplicate Stage 2-B phrase")
        seen_phrases.add(phrase)
        if not isinstance(group, str) or not group or canonical != group:
            raise Stage2CSpecialistCVError("Stage 2-B group identity malformed")
        if not isinstance(fold, int) or isinstance(fold, bool) or fold not in range(FOLD_COUNT):
            raise Stage2CSpecialistCVError("Stage 2-B development fold malformed")
        previous = group_fold.setdefault(group, fold)
        if previous != fold:
            raise Stage2CSpecialistCVError("work family spans Stage 2-B development folds")

        features = _validate_features(item.get("features"))
        vocabulary.update(features)
        feature_occurrences += sum(features.values())
        specialists = item.get("specialists")
        if not isinstance(specialists, dict) or set(specialists) != set(SPECIALIST_IDS):
            raise Stage2CSpecialistCVError("Stage 2-B specialist set changed")
        target_sets = {
            specialist_id: _validate_specialist_payload(
                specialist_id, specialists[specialist_id]
            )
            for specialist_id in SPECIALIST_IDS
        }
        fold_records[fold] += 1
        fold_groups[fold].add(group)
        validated.append(
            {
                "phrase_key": phrase,
                "split_group_id": group,
                "development_fold": fold,
                "features": features,
                "target_sets": target_sets,
            }
        )

    if len(group_fold) != PINNED_STAGE2B_WORK_FAMILY_COUNT:
        raise Stage2CSpecialistCVError("Stage 2-B work-family count changed")
    if {str(i): fold_records[i] for i in range(FOLD_COUNT)} != EXPECTED_FOLD_RECORD_DISTRIBUTION:
        raise Stage2CSpecialistCVError("observed Stage 2-B fold record counts changed")
    if {str(i): len(fold_groups[i]) for i in range(FOLD_COUNT)} != EXPECTED_FOLD_WORK_FAMILY_DISTRIBUTION:
        raise Stage2CSpecialistCVError("observed Stage 2-B fold family counts changed")
    if len(vocabulary) != PINNED_STAGE2B_FEATURE_VOCABULARY_COUNT:
        raise Stage2CSpecialistCVError("observed Stage 2-B feature vocabulary changed")
    if feature_occurrences != PINNED_STAGE2B_FEATURE_OCCURRENCE_COUNT:
        raise Stage2CSpecialistCVError("observed Stage 2-B feature occurrence count changed")
    return sorted(validated, key=lambda item: item["phrase_key"])


def _fit_specialist_nb(
    rows: list[dict[str, Any]],
    specialist_id: str,
    *,
    alpha: float,
) -> dict[str, object]:
    if specialist_id not in SPECIALIST_IDS:
        raise Stage2CSpecialistCVError("unsupported specialist")
    if not isinstance(alpha, (int, float)) or isinstance(alpha, bool) or not math.isfinite(alpha) or alpha <= 0:
        raise Stage2CSpecialistCVError("alpha must be finite and positive")
    eligible = [row for row in rows if row["target_sets"][specialist_id]]
    if not eligible:
        raise Stage2CSpecialistCVError("specialist fit set has no eligible records")
    vocabulary = sorted({key for row in eligible for key in row["features"]})
    if not vocabulary:
        raise Stage2CSpecialistCVError("specialist fit vocabulary is empty")

    class_weights: defaultdict[str, float] = defaultdict(float)
    class_token_totals: defaultdict[str, float] = defaultdict(float)
    class_feature_counts: defaultdict[str, defaultdict[str, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    variant_record_count = 0
    for row in eligible:
        targets = row["target_sets"][specialist_id]
        if len(targets) > 1:
            variant_record_count += 1
        weight = 1.0 / len(targets)
        for target in targets:
            class_weights[target] += weight
            for key, count in row["features"].items():
                weighted = weight * count
                class_feature_counts[target][key] += weighted
                class_token_totals[target] += weighted

    classes: list[dict[str, object]] = []
    for target in sorted(class_weights):
        counts = class_feature_counts[target]
        classes.append(
            {
                "class_value": target,
                "class_weight": class_weights[target],
                "token_total": class_token_totals[target],
                "feature_counts": {key: counts[key] for key in sorted(counts)},
            }
        )
    return {
        "implementation_version": MODEL_IMPLEMENTATION_VERSION,
        "specialist_id": specialist_id,
        "alpha": float(alpha),
        "score_semantics": SCORE_SEMANTICS,
        "training_example_count": len(eligible),
        "variant_training_example_count": variant_record_count,
        "vocabulary": vocabulary,
        "classes": classes,
        "calibrated_probability_output": False,
        "production_authority": False,
    }


def _predict_specialist_nb(model: dict[str, object], features: dict[str, int]) -> tuple[str, float]:
    vocabulary = set(model["vocabulary"])
    classes = model["classes"]
    alpha = float(model["alpha"])
    total_weight = sum(float(item["class_weight"]) for item in classes)
    if not vocabulary or total_weight <= 0:
        raise Stage2CSpecialistCVError("specialist model is malformed")
    vocabulary_size = len(vocabulary)
    best: tuple[float, str] | None = None
    for item in classes:
        target = str(item["class_value"])
        class_weight = float(item["class_weight"])
        token_total = float(item["token_total"])
        counts = item["feature_counts"]
        score = math.log(class_weight / total_weight)
        denominator = token_total + alpha * vocabulary_size
        for key, count in features.items():
            if key in vocabulary:
                score += count * math.log((float(counts.get(key, 0.0)) + alpha) / denominator)
        candidate = (score, target)
        if best is None or candidate > best:
            best = candidate
    if best is None:
        raise Stage2CSpecialistCVError("specialist model has no classes")
    return best[1], best[0]


def _majority_target(rows: list[dict[str, Any]], specialist_id: str) -> str:
    weights: defaultdict[str, float] = defaultdict(float)
    for row in rows:
        targets = row["target_sets"][specialist_id]
        if not targets:
            continue
        weight = 1.0 / len(targets)
        for target in targets:
            weights[target] += weight
    if not weights:
        raise Stage2CSpecialistCVError("majority baseline has no eligible labels")
    return max(weights, key=lambda target: (weights[target], target))


def _evaluate_fold(
    records: list[dict[str, Any]],
    specialist_id: str,
    *,
    eval_fold: int,
    alpha: float,
) -> dict[str, int]:
    fit_rows = [row for row in records if row["development_fold"] != eval_fold]
    eval_rows = [
        row
        for row in records
        if row["development_fold"] == eval_fold and row["target_sets"][specialist_id]
    ]
    eligible_fit = [row for row in fit_rows if row["target_sets"][specialist_id]]
    if not eligible_fit or not eval_rows:
        raise Stage2CSpecialistCVError("grouped CV fold lacks eligible fit/eval records")
    fit_groups = {row["split_group_id"] for row in eligible_fit}
    eval_groups = {row["split_group_id"] for row in eval_rows}
    if fit_groups & eval_groups:
        raise Stage2CSpecialistCVError("grouped CV work-family leakage detected")

    model = _fit_specialist_nb(eligible_fit, specialist_id, alpha=alpha)
    correct = 0
    for row in eval_rows:
        prediction, _score = _predict_specialist_nb(model, row["features"])
        if prediction in row["target_sets"][specialist_id]:
            correct += 1
    majority = _majority_target(eligible_fit, specialist_id)
    baseline_correct = sum(
        1 for row in eval_rows if majority in row["target_sets"][specialist_id]
    )
    return {
        "fit_record_count": len(eligible_fit),
        "evaluation_record_count": len(eval_rows),
        "correct_count": correct,
        "majority_baseline_correct_count": baseline_correct,
        "fit_work_family_count": len(fit_groups),
        "evaluation_work_family_count": len(eval_groups),
    }


def _run_specialist_candidates(
    records: list[dict[str, Any]], specialist_id: str
) -> dict[str, object]:
    candidate_results: list[dict[str, object]] = []
    baseline_correct_total: int | None = None
    evaluated_total: int | None = None
    for alpha in CANDIDATE_ALPHAS:
        folds: dict[str, object] = {}
        correct = 0
        evaluated = 0
        baseline_correct = 0
        for fold in range(FOLD_COUNT):
            result = _evaluate_fold(
                records, specialist_id, eval_fold=fold, alpha=float(alpha)
            )
            correct += result["correct_count"]
            evaluated += result["evaluation_record_count"]
            baseline_correct += result["majority_baseline_correct_count"]
            folds[str(fold)] = {
                **result,
                "accuracy": _accuracy(
                    result["correct_count"], result["evaluation_record_count"]
                ),
                "majority_baseline_accuracy": _accuracy(
                    result["majority_baseline_correct_count"],
                    result["evaluation_record_count"],
                ),
            }
        if baseline_correct_total is None:
            baseline_correct_total = baseline_correct
            evaluated_total = evaluated
        elif baseline_correct != baseline_correct_total or evaluated != evaluated_total:
            raise Stage2CSpecialistCVError("candidate evaluation population changed")
        candidate_results.append(
            {
                "alpha": float(alpha),
                "correct_count": correct,
                "evaluation_record_count": evaluated,
                "accuracy": _accuracy(correct, evaluated),
                "folds": folds,
            }
        )

    if baseline_correct_total is None or evaluated_total is None:
        raise Stage2CSpecialistCVError("specialist candidate evaluation did not run")
    selected = max(
        candidate_results,
        key=lambda item: (float(item["accuracy"]), -float(item["alpha"])),
    )
    eligible_record_count = sum(
        1 for row in records if row["target_sets"][specialist_id]
    )
    baseline_accuracy = _accuracy(baseline_correct_total, evaluated_total)
    selected_accuracy = float(selected["accuracy"])
    return {
        "eligible_record_count": eligible_record_count,
        "missing_record_count": len(records) - eligible_record_count,
        "selected_alpha": selected["alpha"],
        "selected_cv_accuracy": selected_accuracy,
        "selected_cv_correct_count": selected["correct_count"],
        "evaluation_record_count": selected["evaluation_record_count"],
        "majority_baseline_accuracy": baseline_accuracy,
        "majority_baseline_correct_count": baseline_correct_total,
        "accuracy_delta_vs_majority": round(selected_accuracy - baseline_accuracy, 12),
        "candidate_metrics": candidate_results,
    }


def _run_once(records: list[dict[str, Any]]) -> dict[str, object]:
    return {
        specialist_id: _run_specialist_candidates(records, specialist_id)
        for specialist_id in SPECIALIST_IDS
    }


def run_stage2c_specialist_grouped_cv(data: object) -> dict[str, object]:
    records = validate_stage2b_private_payload(data)
    forward = _run_once(records)
    reverse = _run_once(list(reversed(records)))
    deterministic_match = _canonical_bytes(forward) == _canonical_bytes(reverse)
    if not deterministic_match:
        raise Stage2CSpecialistCVError("Stage 2-C deterministic rerun mismatch")
    return {
        "schema_version": SUMMARY_SCHEMA,
        "source_corpus": SOURCE_CORPUS,
        "source_revision": PINNED_TAVERN_REVISION,
        "source_stage2b_private_record_manifest_sha256": (
            PINNED_STAGE2B_PRIVATE_RECORD_MANIFEST_SHA256
        ),
        "record_count": PINNED_STAGE2B_RECORD_COUNT,
        "work_family_count": PINNED_STAGE2B_WORK_FAMILY_COUNT,
        "fold_count": FOLD_COUNT,
        "group_plan_manifest_sha256": PINNED_GROUP_PLAN_SHA256,
        "model_implementation_version": MODEL_IMPLEMENTATION_VERSION,
        "model_score_semantics": SCORE_SEMANTICS,
        "candidate_alphas": list(CANDIDATE_ALPHAS),
        "selection_metric": SELECTION_METRIC,
        "selection_policy": SELECTION_POLICY,
        "specialists": forward,
        "deterministic_rerun_match": True,
        "development_model_fitting_started": True,
        "development_scope": "STAGE0_T_TRAIN_GROUPED_CV_ONLY",
        "full_train_final_fit_started": False,
        "original_validation_target_access": False,
        "calibration_target_access": False,
        "holdout_target_access": False,
        "event_level_training_authorized": False,
        "production_authority": False,
        "calibrated_probability_output": False,
        "deterministic_resolver_remains_authoritative": True,
        "result_scope": "TRAIN_ONLY_GROUPED_CV_DIAGNOSTIC",
    }


def run_stage2c_specialist_grouped_cv_from_file(path: str | Path) -> dict[str, object]:
    source = Path(path)
    if source.is_symlink():
        raise Stage2CSpecialistCVError("Stage 2-B private payload symlink rejected")
    meta = source.stat()
    if not stat.S_ISREG(meta.st_mode) or meta.st_size > MAX_PRIVATE_INPUT_BYTES:
        raise Stage2CSpecialistCVError("Stage 2-B private payload must be a bounded regular file")
    data = load_bounded_json(source, max_bytes=MAX_PRIVATE_INPUT_BYTES)
    return run_stage2c_specialist_grouped_cv(data)


def canonical_stage2c_summary_json(data: dict[str, object]) -> str:
    if data.get("schema_version") != SUMMARY_SCHEMA:
        raise Stage2CSpecialistCVError("unsupported Stage 2-C summary schema")
    if data.get("deterministic_rerun_match") is not True:
        raise Stage2CSpecialistCVError("Stage 2-C summary lacks deterministic rerun PASS")
    for field in (
        "full_train_final_fit_started",
        "original_validation_target_access",
        "calibration_target_access",
        "holdout_target_access",
        "event_level_training_authorized",
        "production_authority",
        "calibrated_probability_output",
    ):
        if data.get(field) is not False:
            raise Stage2CSpecialistCVError(f"Stage 2-C summary authority violation: {field}")
    if data.get("deterministic_resolver_remains_authoritative") is not True:
        raise Stage2CSpecialistCVError("deterministic resolver authority changed")
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
