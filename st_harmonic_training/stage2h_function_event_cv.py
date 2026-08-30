from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .offline_experiment import require_locked_runtime
from .safe_ingest import load_bounded_json
from .stage1e_internal_cv import FOLD_COUNT, PINNED_GROUP_PLAN_SHA256
from .stage2c_contract import CANDIDATE_ALPHAS
from .stage2c_specialist_cv import validate_stage2b_private_payload
from .stage2g_function_onset_events import (
    FUNCTION_SPECIALIST_TARGET_SHAPE,
    MATERIALIZATION_SCHEMA as STAGE2G_SCHEMA,
    build_stage2g_summary,
)

CONTRACT_SCHEMA = "st-stage2h-function-event-grouped-cv-contract-v1"
SUMMARY_SCHEMA = "st-stage2h-function-event-grouped-cv-summary-v1"
SOURCE_CORPUS = "TAVERN_REVIEWED_694"
MODEL_IMPLEMENTATION_VERSION = "stage2h-multinomial-nb-v1"
SCORE_SEMANTICS = "MODEL_SCORE_NOT_PROBABILITY"
SELECTION_METRIC = "POOLED_EVENT_ACCURACY"
SELECTION_POLICY = "MAX_METRIC_THEN_LOWEST_ALPHA"
EXPECTED_STAGE2G_PRIVATE_EVENT_MANIFEST_SHA256 = (
    "d7bbd514ec85b87aee423cae9dce39c74e634ab2f1040fed82af0e25105f255d"
)
EXPECTED_STAGE2G_EVENT_COUNT = 1854
EXPECTED_STAGE2G_MATERIALIZABLE_SOURCE_PATH_COUNT = 363
EXPECTED_STAGE2G_CANDIDATE_RECORD_COUNT = 355
MAX_PRIVATE_BYTES = 64 * 1024 * 1024


class Stage2HFunctionEventCVError(ValueError):
    pass


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def build_stage2h_contract() -> dict[str, object]:
    return {
        "schema_version": CONTRACT_SCHEMA,
        "source_corpus": SOURCE_CORPUS,
        "eligible_original_partition": "TRAIN",
        "source_stage1e_group_plan_manifest_sha256": PINNED_GROUP_PLAN_SHA256,
        "source_stage2g_private_event_manifest_sha256": (
            EXPECTED_STAGE2G_PRIVATE_EVENT_MANIFEST_SHA256
        ),
        "source_stage2g_materialized_event_count": EXPECTED_STAGE2G_EVENT_COUNT,
        "source_stage2g_materializable_source_path_count": (
            EXPECTED_STAGE2G_MATERIALIZABLE_SOURCE_PATH_COUNT
        ),
        "source_stage2g_candidate_record_count": EXPECTED_STAGE2G_CANDIDATE_RECORD_COUNT,
        "function_specialist_target_shape": FUNCTION_SPECIALIST_TARGET_SHAPE,
        "feature_scope": "STAGE2B_TRAIN_PHRASE_CONTEXT_FEATURES",
        "event_identity_scope": "STAGE2G_TRAIN_FUNCTION_ONSET_EVENTS",
        "grouping_unit": "SPLIT_GROUP_ID_WORK_FAMILY",
        "fold_source": "STAGE1E_DEVELOPMENT_FOLD",
        "fold_count": FOLD_COUNT,
        "candidate_alphas": list(CANDIDATE_ALPHAS),
        "selection_metric": SELECTION_METRIC,
        "selection_policy": SELECTION_POLICY,
        "model_implementation_version": MODEL_IMPLEMENTATION_VERSION,
        "score_semantics": SCORE_SEMANTICS,
        "event_random_split_authorized": False,
        "phrase_random_split_authorized": False,
        "cross_work_family_leakage_authorized": False,
        "non_train_annotation_bodies_materialized": False,
        "original_validation_target_access": False,
        "calibration_target_access": False,
        "holdout_target_access": False,
        "duration_inference_authorized": False,
        "segment_boundary_inference_authorized": False,
        "function_token_rewrite_authorized": False,
        "joined_harmonic_labels_authoritative": False,
        "cv_model_fit_authorized": True,
        "full_train_final_fit_started": False,
        "production_authority": False,
        "deterministic_resolver_remains_authoritative": True,
    }


def validate_stage2h_contract(data: object) -> dict[str, object]:
    expected = build_stage2h_contract()
    if not isinstance(data, dict) or data != expected:
        raise Stage2HFunctionEventCVError("Stage 2-H contract differs from frozen contract")
    return data


def _validate_stage2g_private_payload(data: object) -> list[dict[str, Any]]:
    if not isinstance(data, dict) or data.get("schema_version") != STAGE2G_SCHEMA:
        raise Stage2HFunctionEventCVError("unsupported Stage 2-G private payload schema")
    # Reuse Stage 2-G's full fail-closed boundary validation first.
    build_stage2g_summary(data)
    if data.get("private_event_manifest_sha256") != EXPECTED_STAGE2G_PRIVATE_EVENT_MANIFEST_SHA256:
        raise Stage2HFunctionEventCVError("Stage 2-G private event manifest changed")
    if data.get("materialized_event_count") != EXPECTED_STAGE2G_EVENT_COUNT:
        raise Stage2HFunctionEventCVError("Stage 2-G event count changed")
    if data.get("materialized_source_path_count") != EXPECTED_STAGE2G_MATERIALIZABLE_SOURCE_PATH_COUNT:
        raise Stage2HFunctionEventCVError("Stage 2-G materializable path count changed")
    if data.get("onset_carrier_candidate_record_count") != EXPECTED_STAGE2G_CANDIDATE_RECORD_COUNT:
        raise Stage2HFunctionEventCVError("Stage 2-G candidate record count changed")
    events = data.get("events")
    if not isinstance(events, list) or len(events) != EXPECTED_STAGE2G_EVENT_COUNT:
        raise Stage2HFunctionEventCVError("Stage 2-G private events malformed")
    if _canonical_sha256(events) != EXPECTED_STAGE2G_PRIVATE_EVENT_MANIFEST_SHA256:
        raise Stage2HFunctionEventCVError("Stage 2-G private event body digest mismatch")
    return events


def _join_event_rows(
    stage2b_data: object, stage2g_data: object
) -> list[dict[str, Any]]:
    phrase_rows = validate_stage2b_private_payload(stage2b_data)
    events = _validate_stage2g_private_payload(stage2g_data)
    by_phrase = {str(row["phrase_key"]): row for row in phrase_rows}
    joined: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    group_fold: dict[str, int] = {}
    for event in events:
        if not isinstance(event, dict):
            raise Stage2HFunctionEventCVError("event row malformed")
        phrase = event.get("phrase_key")
        group = event.get("split_group_id")
        fold = event.get("development_fold")
        event_id = event.get("carrier_event_id")
        target = event.get("function_token")
        source = event.get("source")
        if not isinstance(phrase, str) or phrase not in by_phrase:
            raise Stage2HFunctionEventCVError("event phrase lacks Stage 2-B feature row")
        phrase_row = by_phrase[phrase]
        if group != phrase_row["split_group_id"] or fold != phrase_row["development_fold"]:
            raise Stage2HFunctionEventCVError("event group/fold differs from Stage 2-B identity")
        if not isinstance(group, str) or not isinstance(fold, int) or fold not in range(FOLD_COUNT):
            raise Stage2HFunctionEventCVError("event group/fold malformed")
        if not isinstance(event_id, str) or not event_id or event_id in seen_ids:
            raise Stage2HFunctionEventCVError("event identity invalid/duplicate")
        seen_ids.add(event_id)
        if not isinstance(target, str) or not target:
            raise Stage2HFunctionEventCVError("Function event target malformed")
        if source not in {"A", "B"}:
            raise Stage2HFunctionEventCVError("A/B provenance malformed")
        previous = group_fold.setdefault(group, fold)
        if previous != fold:
            raise Stage2HFunctionEventCVError("work family spans development folds")
        joined.append(
            {
                "event_id": event_id,
                "phrase_key": phrase,
                "split_group_id": group,
                "development_fold": fold,
                "source": source,
                "features": phrase_row["features"],
                "target": target,
            }
        )
    if len(joined) != EXPECTED_STAGE2G_EVENT_COUNT:
        raise Stage2HFunctionEventCVError("joined event count changed")
    return joined


def _fit_nb(rows: list[dict[str, Any]], alpha: float) -> dict[str, Any]:
    if not rows:
        raise Stage2HFunctionEventCVError("empty fit rows")
    if not isinstance(alpha, (int, float)) or isinstance(alpha, bool) or not math.isfinite(alpha) or alpha <= 0:
        raise Stage2HFunctionEventCVError("alpha must be finite and positive")
    vocabulary = sorted({key for row in rows for key in row["features"]})
    if not vocabulary:
        raise Stage2HFunctionEventCVError("fit vocabulary empty")
    class_counts: Counter[str] = Counter()
    class_token_totals: Counter[str] = Counter()
    class_features: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        target = str(row["target"])
        class_counts[target] += 1
        for key, count in row["features"].items():
            class_features[target][key] += int(count)
            class_token_totals[target] += int(count)
    return {
        "alpha": float(alpha),
        "vocabulary": vocabulary,
        "class_counts": class_counts,
        "class_token_totals": class_token_totals,
        "class_features": class_features,
    }


def _predict_nb(model: dict[str, Any], features: dict[str, int]) -> str:
    vocabulary = set(model["vocabulary"])
    vocabulary_size = len(vocabulary)
    class_counts: Counter[str] = model["class_counts"]
    total_examples = sum(class_counts.values())
    best: tuple[float, str] | None = None
    for target in sorted(class_counts):
        score = math.log(class_counts[target] / total_examples)
        denom = model["class_token_totals"][target] + model["alpha"] * vocabulary_size
        counts = model["class_features"][target]
        for key, count in features.items():
            if key in vocabulary:
                score += int(count) * math.log((counts.get(key, 0) + model["alpha"]) / denom)
        candidate = (score, target)
        if best is None or candidate > best:
            best = candidate
    if best is None:
        raise Stage2HFunctionEventCVError("model has no classes")
    return best[1]


def _majority_target(rows: list[dict[str, Any]]) -> str:
    counts = Counter(str(row["target"]) for row in rows)
    if not counts:
        raise Stage2HFunctionEventCVError("majority baseline has no labels")
    return max(counts, key=lambda value: (counts[value], value))


def _accuracy(correct: int, total: int) -> float:
    if total <= 0:
        raise Stage2HFunctionEventCVError("accuracy denominator must be positive")
    return round(correct / total, 12)


def run_stage2h_grouped_cv(stage2b_data: object, stage2g_data: object) -> dict[str, object]:
    validate_stage2h_contract(build_stage2h_contract())
    rows = _join_event_rows(stage2b_data, stage2g_data)
    fold_event_counts = Counter(int(row["development_fold"]) for row in rows)
    fold_group_counts: dict[int, set[str]] = defaultdict(set)
    for row in rows:
        fold_group_counts[int(row["development_fold"])].add(str(row["split_group_id"]))

    candidate_results: list[dict[str, object]] = []
    for alpha in CANDIDATE_ALPHAS:
        total_correct = 0
        total_majority_correct = 0
        total_eval = 0
        folds: list[dict[str, object]] = []
        for fold in range(FOLD_COUNT):
            fit_rows = [row for row in rows if row["development_fold"] != fold]
            eval_rows = [row for row in rows if row["development_fold"] == fold]
            fit_groups = {str(row["split_group_id"]) for row in fit_rows}
            eval_groups = {str(row["split_group_id"]) for row in eval_rows}
            if fit_groups & eval_groups:
                raise Stage2HFunctionEventCVError("work-family leakage across fit/eval")
            model = _fit_nb(fit_rows, float(alpha))
            majority = _majority_target(fit_rows)
            correct = sum(_predict_nb(model, row["features"]) == row["target"] for row in eval_rows)
            majority_correct = sum(majority == row["target"] for row in eval_rows)
            total_correct += correct
            total_majority_correct += majority_correct
            total_eval += len(eval_rows)
            folds.append(
                {
                    "fold": fold,
                    "fit_event_count": len(fit_rows),
                    "eval_event_count": len(eval_rows),
                    "fit_work_family_count": len(fit_groups),
                    "eval_work_family_count": len(eval_groups),
                    "accuracy": _accuracy(correct, len(eval_rows)),
                    "majority_accuracy": _accuracy(majority_correct, len(eval_rows)),
                }
            )
        candidate_results.append(
            {
                "alpha": float(alpha),
                "pooled_accuracy": _accuracy(total_correct, total_eval),
                "pooled_majority_accuracy": _accuracy(total_majority_correct, total_eval),
                "folds": folds,
            }
        )

    selected = max(
        candidate_results,
        key=lambda item: (float(item["pooled_accuracy"]), -float(item["alpha"])),
    )
    summary = {
        "schema_version": SUMMARY_SCHEMA,
        "source_corpus": SOURCE_CORPUS,
        "eligible_original_partition": "TRAIN",
        "source_stage1e_group_plan_manifest_sha256": PINNED_GROUP_PLAN_SHA256,
        "source_stage2g_private_event_manifest_sha256": EXPECTED_STAGE2G_PRIVATE_EVENT_MANIFEST_SHA256,
        "materialized_event_count": len(rows),
        "fold_event_distribution": {str(i): fold_event_counts[i] for i in range(FOLD_COUNT)},
        "fold_work_family_distribution": {str(i): len(fold_group_counts[i]) for i in range(FOLD_COUNT)},
        "feature_scope": "STAGE2B_TRAIN_PHRASE_CONTEXT_FEATURES",
        "target_shape": FUNCTION_SPECIALIST_TARGET_SHAPE,
        "selection_metric": SELECTION_METRIC,
        "selection_policy": SELECTION_POLICY,
        "selected_alpha": selected["alpha"],
        "selected_pooled_accuracy": selected["pooled_accuracy"],
        "selected_pooled_majority_accuracy": selected["pooled_majority_accuracy"],
        "selected_delta_vs_majority": round(
            float(selected["pooled_accuracy"]) - float(selected["pooled_majority_accuracy"]), 12
        ),
        "candidate_results": candidate_results,
        "score_semantics": SCORE_SEMANTICS,
        "calibrated_probability_output": False,
        "event_random_split_used": False,
        "phrase_random_split_used": False,
        "cross_work_family_leakage": False,
        "non_train_annotation_bodies_materialized": False,
        "original_validation_target_access": False,
        "calibration_target_access": False,
        "holdout_target_access": False,
        "duration_inference_used": False,
        "segment_boundary_inference_used": False,
        "function_token_rewrite_used": False,
        "joined_harmonic_labels_authoritative": False,
        "cv_model_fit_performed": True,
        "full_train_final_fit_started": False,
        "production_authority": False,
        "deterministic_resolver_remains_authoritative": True,
    }
    rendered = json.dumps(summary, sort_keys=True, ensure_ascii=False)
    for private_key in ("function_token", "phrase_key", "carrier_event_id", "source_annotation_sha256"):
        if private_key in rendered:
            raise Stage2HFunctionEventCVError("shareable Stage 2-H summary leaks private event data")
    return summary


def run_stage2h_grouped_cv_from_files(
    stage2b_private_path: str | Path,
    stage2g_private_path: str | Path,
) -> dict[str, object]:
    require_locked_runtime()
    stage2b = load_bounded_json(stage2b_private_path, max_bytes=MAX_PRIVATE_BYTES)
    stage2g = load_bounded_json(stage2g_private_path, max_bytes=MAX_PRIVATE_BYTES)
    return run_stage2h_grouped_cv(stage2b, stage2g)


def canonical_stage2h_json(data: dict[str, object]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
