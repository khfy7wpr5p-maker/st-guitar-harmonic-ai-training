from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Any

from .offline_experiment import require_locked_runtime
from .safe_ingest import load_bounded_json
from .stage1e_internal_cv import FOLD_COUNT, PINNED_GROUP_PLAN_SHA256
from .stage2c_contract import CANDIDATE_ALPHAS
from .stage2c_specialist_cv import validate_stage2b_private_payload
from .stage2h_function_event_cv import (
    EXPECTED_STAGE2G_EVENT_COUNT,
    EXPECTED_STAGE2G_PRIVATE_EVENT_MANIFEST_SHA256,
    SCORE_SEMANTICS,
    SELECTION_METRIC,
    SELECTION_POLICY,
    _accuracy,
    _fit_nb,
    _majority_target,
    _predict_nb,
    _validate_stage2g_private_payload,
)
from .stage2i_function_event_feature_audit import build_stage2i_contract, validate_stage2i_contract

CONTRACT_SCHEMA = "st-stage2j-function-event-index-cv-contract-v1"
SUMMARY_SCHEMA = "st-stage2j-function-event-index-cv-summary-v1"
SOURCE_CORPUS = "TAVERN_REVIEWED_694"
MODEL_IMPLEMENTATION_VERSION = "stage2j-multinomial-nb-event-index-v1"
AUTHORIZED_EVENT_FEATURES = (
    "FUNCTION_EVENT_INDEX",
    "CARRIER_HARMONIC_EVENT_INDEX",
)
FEATURE_PREFIX = "stage2j:event_index:"
MAX_PRIVATE_BYTES = 64 * 1024 * 1024


class Stage2JFunctionEventIndexCVError(ValueError):
    pass


def build_stage2j_contract() -> dict[str, object]:
    audit = validate_stage2i_contract(build_stage2i_contract())
    if audit.get("audit_scope") != "EXISTING_STAGE2G_EVENT_IDENTITY_AND_ORDER_FIELDS_ONLY":
        raise Stage2JFunctionEventIndexCVError("Stage 2-I audit scope changed")
    return {
        "schema_version": CONTRACT_SCHEMA,
        "source_corpus": SOURCE_CORPUS,
        "eligible_original_partition": "TRAIN",
        "source_stage1e_group_plan_manifest_sha256": PINNED_GROUP_PLAN_SHA256,
        "source_stage2g_private_event_manifest_sha256": EXPECTED_STAGE2G_PRIVATE_EVENT_MANIFEST_SHA256,
        "source_stage2g_materialized_event_count": EXPECTED_STAGE2G_EVENT_COUNT,
        "source_stage2i_audit_scope": audit["audit_scope"],
        "authorized_event_features": list(AUTHORIZED_EVENT_FEATURES),
        "event_feature_encoding": "EXACT_NONNEGATIVE_INTEGER_AS_CATEGORICAL_ONE_HOT",
        "phrase_context_features_preserved": True,
        "source_provenance_as_model_feature_authorized": False,
        "carrier_source_order_as_model_feature_authorized": False,
        "index_gap_feature_authorized": False,
        "explicit_onset_feature_authorized": False,
        "duration_feature_authorized": False,
        "segment_boundary_feature_authorized": False,
        "local_harmonic_label_feature_authorized": False,
        "local_score_context_feature_authorized": False,
        "function_token_rewrite_authorized": False,
        "event_random_split_authorized": False,
        "phrase_random_split_authorized": False,
        "cross_work_family_leakage_authorized": False,
        "fold_source": "STAGE1E_DEVELOPMENT_FOLD",
        "fold_count": FOLD_COUNT,
        "candidate_alphas": list(CANDIDATE_ALPHAS),
        "selection_metric": SELECTION_METRIC,
        "selection_policy": SELECTION_POLICY,
        "model_implementation_version": MODEL_IMPLEMENTATION_VERSION,
        "score_semantics": SCORE_SEMANTICS,
        "cv_model_fit_authorized": True,
        "full_train_final_fit_started": False,
        "original_validation_target_access": False,
        "calibration_target_access": False,
        "holdout_target_access": False,
        "production_authority": False,
        "deterministic_resolver_remains_authoritative": True,
    }


def validate_stage2j_contract(data: object) -> dict[str, object]:
    expected = build_stage2j_contract()
    if not isinstance(data, dict) or data != expected:
        raise Stage2JFunctionEventIndexCVError("Stage 2-J contract differs from frozen contract")
    return data


def _nonnegative_index(event: dict[str, Any], field: str) -> int:
    value = event.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise Stage2JFunctionEventIndexCVError(f"invalid event index: {field}")
    return value


def _index_feature_vector(base: object, function_index: int, harmonic_index: int) -> dict[str, int]:
    if not isinstance(base, dict) or not base:
        raise Stage2JFunctionEventIndexCVError("phrase feature vector malformed")
    result: dict[str, int] = {}
    for key, value in base.items():
        if not isinstance(key, str) or not key or key.startswith(FEATURE_PREFIX):
            raise Stage2JFunctionEventIndexCVError("phrase feature key collides with Stage 2-J namespace")
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise Stage2JFunctionEventIndexCVError("phrase feature count malformed")
        if value:
            result[key] = value
    if not result:
        raise Stage2JFunctionEventIndexCVError("phrase feature vector empty")
    result[f"{FEATURE_PREFIX}function={function_index}"] = 1
    result[f"{FEATURE_PREFIX}harmonic={harmonic_index}"] = 1
    return dict(sorted(result.items()))


def _join_rows(stage2b_data: object, stage2g_data: object) -> list[dict[str, Any]]:
    phrase_rows = validate_stage2b_private_payload(stage2b_data)
    events = _validate_stage2g_private_payload(stage2g_data)
    by_phrase = {str(row["phrase_key"]): row for row in phrase_rows}
    joined: list[dict[str, Any]] = []
    group_fold: dict[str, int] = {}
    seen_ids: set[str] = set()

    for event in events:
        if not isinstance(event, dict):
            raise Stage2JFunctionEventIndexCVError("event row malformed")
        phrase = event.get("phrase_key")
        group = event.get("split_group_id")
        fold = event.get("development_fold")
        event_id = event.get("carrier_event_id")
        target = event.get("function_token")
        if not isinstance(phrase, str) or phrase not in by_phrase:
            raise Stage2JFunctionEventIndexCVError("event lacks frozen Stage 2-B phrase features")
        phrase_row = by_phrase[phrase]
        if group != phrase_row["split_group_id"] or fold != phrase_row["development_fold"]:
            raise Stage2JFunctionEventIndexCVError("event identity differs from Stage 2-B identity")
        if not isinstance(group, str) or not isinstance(fold, int) or isinstance(fold, bool) or fold not in range(FOLD_COUNT):
            raise Stage2JFunctionEventIndexCVError("event group/fold malformed")
        if not isinstance(event_id, str) or not event_id or event_id in seen_ids:
            raise Stage2JFunctionEventIndexCVError("event identity invalid/duplicate")
        seen_ids.add(event_id)
        if not isinstance(target, str) or not target:
            raise Stage2JFunctionEventIndexCVError("Function target malformed")
        function_index = _nonnegative_index(event, "function_event_index")
        harmonic_index = _nonnegative_index(event, "carrier_harmonic_event_index")
        previous = group_fold.setdefault(group, fold)
        if previous != fold:
            raise Stage2JFunctionEventIndexCVError("work family spans development folds")
        joined.append(
            {
                "event_id": event_id,
                "split_group_id": group,
                "development_fold": fold,
                "target": target,
                "phrase_features": dict(phrase_row["features"]),
                "index_features": _index_feature_vector(
                    phrase_row["features"], function_index, harmonic_index
                ),
            }
        )
    if len(joined) != EXPECTED_STAGE2G_EVENT_COUNT:
        raise Stage2JFunctionEventIndexCVError("joined event count changed")
    return joined


def _evaluate(rows: list[dict[str, Any]], feature_field: str) -> dict[str, object]:
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
                raise Stage2JFunctionEventIndexCVError("work-family leakage across fit/eval")
            model_rows = [dict(row, features=row[feature_field]) for row in fit_rows]
            eval_model_rows = [dict(row, features=row[feature_field]) for row in eval_rows]
            model = _fit_nb(model_rows, float(alpha))
            majority = _majority_target(model_rows)
            correct = sum(_predict_nb(model, row["features"]) == row["target"] for row in eval_model_rows)
            majority_correct = sum(majority == row["target"] for row in eval_model_rows)
            total_correct += correct
            total_majority_correct += majority_correct
            total_eval += len(eval_model_rows)
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
    return {
        "selected_alpha": selected["alpha"],
        "selected_pooled_accuracy": selected["pooled_accuracy"],
        "selected_pooled_majority_accuracy": selected["pooled_majority_accuracy"],
        "selected_delta_vs_majority": round(
            float(selected["pooled_accuracy"]) - float(selected["pooled_majority_accuracy"]), 12
        ),
        "candidate_results": candidate_results,
    }


def run_stage2j_grouped_cv(stage2b_data: object, stage2g_data: object) -> dict[str, object]:
    validate_stage2j_contract(build_stage2j_contract())
    rows = _join_rows(stage2b_data, stage2g_data)
    fold_events = Counter(int(row["development_fold"]) for row in rows)
    fold_groups: dict[int, set[str]] = defaultdict(set)
    for row in rows:
        fold_groups[int(row["development_fold"])].add(str(row["split_group_id"]))

    phrase_only = _evaluate(rows, "phrase_features")
    index_augmented = _evaluate(rows, "index_features")
    improvement = round(
        float(index_augmented["selected_pooled_accuracy"])
        - float(phrase_only["selected_pooled_accuracy"]),
        12,
    )

    summary = {
        "schema_version": SUMMARY_SCHEMA,
        "source_corpus": SOURCE_CORPUS,
        "eligible_original_partition": "TRAIN",
        "source_stage1e_group_plan_manifest_sha256": PINNED_GROUP_PLAN_SHA256,
        "source_stage2g_private_event_manifest_sha256": EXPECTED_STAGE2G_PRIVATE_EVENT_MANIFEST_SHA256,
        "materialized_event_count": len(rows),
        "fold_event_distribution": {str(i): fold_events[i] for i in range(FOLD_COUNT)},
        "fold_work_family_distribution": {str(i): len(fold_groups[i]) for i in range(FOLD_COUNT)},
        "authorized_event_features": list(AUTHORIZED_EVENT_FEATURES),
        "event_feature_encoding": "EXACT_NONNEGATIVE_INTEGER_AS_CATEGORICAL_ONE_HOT",
        "phrase_only_reference": phrase_only,
        "index_augmented": index_augmented,
        "index_feature_delta_vs_phrase_only": improvement,
        "score_semantics": SCORE_SEMANTICS,
        "calibrated_probability_output": False,
        "source_provenance_as_model_feature_used": False,
        "carrier_source_order_as_model_feature_used": False,
        "index_gap_feature_used": False,
        "explicit_onset_feature_used": False,
        "duration_feature_used": False,
        "segment_boundary_feature_used": False,
        "local_harmonic_label_feature_used": False,
        "local_score_context_feature_used": False,
        "function_token_rewrite_used": False,
        "event_random_split_used": False,
        "phrase_random_split_used": False,
        "cross_work_family_leakage": False,
        "cv_model_fit_performed": True,
        "full_train_final_fit_started": False,
        "original_validation_target_access": False,
        "calibration_target_access": False,
        "holdout_target_access": False,
        "production_authority": False,
        "deterministic_resolver_remains_authoritative": True,
    }
    rendered = json.dumps(summary, sort_keys=True, ensure_ascii=False)
    for private_key in ("phrase_key", "carrier_event_id", "function_token", "source_annotation_sha256"):
        if f'"{private_key}"' in rendered:
            raise Stage2JFunctionEventIndexCVError("shareable Stage 2-J summary leaks private event data")
    return summary


def run_stage2j_grouped_cv_from_files(stage2b_private_path: str | Path, stage2g_private_path: str | Path) -> dict[str, object]:
    require_locked_runtime()
    stage2b = load_bounded_json(stage2b_private_path, max_bytes=MAX_PRIVATE_BYTES)
    stage2g = load_bounded_json(stage2g_private_path, max_bytes=MAX_PRIVATE_BYTES)
    return run_stage2j_grouped_cv(stage2b, stage2g)


def canonical_stage2j_json(data: dict[str, object]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
