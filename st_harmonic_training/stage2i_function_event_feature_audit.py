from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path
from statistics import median
from typing import Any

from .offline_experiment import require_locked_runtime
from .safe_ingest import load_bounded_json
from .stage1e_internal_cv import FOLD_COUNT, PINNED_GROUP_PLAN_SHA256
from .stage2h_function_event_cv import (
    EXPECTED_STAGE2G_EVENT_COUNT,
    EXPECTED_STAGE2G_PRIVATE_EVENT_MANIFEST_SHA256,
    _validate_stage2g_private_payload,
)

CONTRACT_SCHEMA = "st-stage2i-function-event-feature-alignment-audit-contract-v1"
SUMMARY_SCHEMA = "st-stage2i-function-event-feature-alignment-audit-summary-v1"
SOURCE_CORPUS = "TAVERN_REVIEWED_694"
MAX_PRIVATE_BYTES = 64 * 1024 * 1024


class Stage2IFunctionEventFeatureAuditError(ValueError):
    pass


def build_stage2i_contract() -> dict[str, object]:
    return {
        "schema_version": CONTRACT_SCHEMA,
        "source_corpus": SOURCE_CORPUS,
        "eligible_original_partition": "TRAIN",
        "source_stage1e_group_plan_manifest_sha256": PINNED_GROUP_PLAN_SHA256,
        "source_stage2g_private_event_manifest_sha256": EXPECTED_STAGE2G_PRIVATE_EVENT_MANIFEST_SHA256,
        "source_stage2g_materialized_event_count": EXPECTED_STAGE2G_EVENT_COUNT,
        "audit_scope": "EXISTING_STAGE2G_EVENT_IDENTITY_AND_ORDER_FIELDS_ONLY",
        "audited_fields": [
            "function_event_index",
            "carrier_harmonic_event_index",
            "carrier_source_order_index",
            "source",
        ],
        "explicit_onset_value_available_in_stage2g_payload": False,
        "duration_available_in_stage2g_payload": False,
        "segment_boundary_available_in_stage2g_payload": False,
        "local_harmonic_label_context_available_in_stage2g_payload": False,
        "local_score_context_available_in_stage2g_payload": False,
        "source_provenance_as_model_feature_authorized": False,
        "feature_materialization_authorized": False,
        "model_training_started": False,
        "model_selection_started": False,
        "full_train_final_fit_started": False,
        "original_validation_target_access": False,
        "calibration_target_access": False,
        "holdout_target_access": False,
        "function_token_rewrite_authorized": False,
        "duration_inference_authorized": False,
        "segment_boundary_inference_authorized": False,
        "production_authority": False,
        "deterministic_resolver_remains_authoritative": True,
    }


def validate_stage2i_contract(data: object) -> dict[str, object]:
    expected = build_stage2i_contract()
    if not isinstance(data, dict) or data != expected:
        raise Stage2IFunctionEventFeatureAuditError("Stage 2-I contract differs from frozen audit contract")
    return data


def _require_nonnegative_int(event: dict[str, Any], field: str) -> int:
    value = event.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise Stage2IFunctionEventFeatureAuditError(f"invalid {field}")
    return value


def run_stage2i_audit(stage2g_data: object) -> dict[str, object]:
    validate_stage2i_contract(build_stage2i_contract())
    events = _validate_stage2g_private_payload(stage2g_data)
    paths: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    fold_events: Counter[int] = Counter()
    source_events: Counter[str] = Counter()
    target_counts: Counter[str] = Counter()

    for raw in events:
        event = dict(raw)
        phrase = event.get("phrase_key")
        source = event.get("source")
        fold = event.get("development_fold")
        target = event.get("function_token")
        if not isinstance(phrase, str) or not phrase or source not in {"A", "B"}:
            raise Stage2IFunctionEventFeatureAuditError("event identity/provenance malformed")
        if not isinstance(fold, int) or isinstance(fold, bool) or fold not in range(FOLD_COUNT):
            raise Stage2IFunctionEventFeatureAuditError("event fold malformed")
        if not isinstance(target, str) or not target:
            raise Stage2IFunctionEventFeatureAuditError("Function target malformed")
        _require_nonnegative_int(event, "function_event_index")
        _require_nonnegative_int(event, "carrier_harmonic_event_index")
        _require_nonnegative_int(event, "carrier_source_order_index")
        paths[(phrase, str(source))].append(event)
        fold_events[fold] += 1
        source_events[str(source)] += 1
        target_counts[target] += 1

    if len(events) != EXPECTED_STAGE2G_EVENT_COUNT:
        raise Stage2IFunctionEventFeatureAuditError("event count changed")

    path_event_counts: list[int] = []
    harmonic_gap_event_count = 0
    harmonic_function_index_divergence_count = 0
    function_index_sequence_valid_path_count = 0
    harmonic_index_strict_path_count = 0
    source_order_strict_path_count = 0

    for rows in paths.values():
        rows.sort(key=lambda item: int(item["function_event_index"]))
        function_indices = [int(item["function_event_index"]) for item in rows]
        harmonic_indices = [int(item["carrier_harmonic_event_index"]) for item in rows]
        source_orders = [int(item["carrier_source_order_index"]) for item in rows]
        path_event_counts.append(len(rows))
        if function_indices == list(range(len(rows))):
            function_index_sequence_valid_path_count += 1
        else:
            raise Stage2IFunctionEventFeatureAuditError("Function event index is not consecutive from zero")
        if all(b > a for a, b in zip(harmonic_indices, harmonic_indices[1:])):
            harmonic_index_strict_path_count += 1
        else:
            raise Stage2IFunctionEventFeatureAuditError("harmonic carrier index is not strictly increasing")
        if all(b > a for a, b in zip(source_orders, source_orders[1:])):
            source_order_strict_path_count += 1
        else:
            raise Stage2IFunctionEventFeatureAuditError("source order index is not strictly increasing")
        harmonic_gap_event_count += sum((b - a) > 1 for a, b in zip(harmonic_indices, harmonic_indices[1:]))
        harmonic_function_index_divergence_count += sum(
            h != f for h, f in zip(harmonic_indices, function_indices)
        )

    unique_targets = len(target_counts)
    singleton_targets = sum(count == 1 for count in target_counts.values())
    top_target_count = max(target_counts.values()) if target_counts else 0
    path_count = len(paths)
    phrase_count = len({phrase for phrase, _ in paths})

    summary = {
        "schema_version": SUMMARY_SCHEMA,
        "source_corpus": SOURCE_CORPUS,
        "eligible_original_partition": "TRAIN",
        "source_stage1e_group_plan_manifest_sha256": PINNED_GROUP_PLAN_SHA256,
        "source_stage2g_private_event_manifest_sha256": EXPECTED_STAGE2G_PRIVATE_EVENT_MANIFEST_SHA256,
        "materialized_event_count": len(events),
        "source_path_count": path_count,
        "phrase_count": phrase_count,
        "source_event_counts": {"A": source_events["A"], "B": source_events["B"]},
        "fold_event_distribution": {str(i): fold_events[i] for i in range(FOLD_COUNT)},
        "path_event_count_min": min(path_event_counts),
        "path_event_count_max": max(path_event_counts),
        "path_event_count_median": float(median(path_event_counts)),
        "path_event_count_mean": round(sum(path_event_counts) / path_count, 12),
        "function_event_index_coverage": 1.0,
        "carrier_harmonic_event_index_coverage": 1.0,
        "carrier_source_order_index_coverage": 1.0,
        "function_index_sequence_valid_path_count": function_index_sequence_valid_path_count,
        "harmonic_index_strict_path_count": harmonic_index_strict_path_count,
        "source_order_strict_path_count": source_order_strict_path_count,
        "harmonic_gap_event_count": harmonic_gap_event_count,
        "harmonic_function_index_divergence_count": harmonic_function_index_divergence_count,
        "unique_function_token_count": unique_targets,
        "singleton_function_token_count": singleton_targets,
        "largest_function_class_share": round(top_target_count / len(events), 12),
        "audit_supported_feature_candidates": [
            "FUNCTION_EVENT_INDEX",
            "CARRIER_HARMONIC_EVENT_INDEX",
        ],
        "format_sensitive_audit_only_fields": ["CARRIER_SOURCE_ORDER_INDEX"],
        "source_provenance_as_model_feature_authorized": False,
        "explicit_onset_value_available_in_stage2g_payload": False,
        "duration_available_in_stage2g_payload": False,
        "segment_boundary_available_in_stage2g_payload": False,
        "local_harmonic_label_context_available_in_stage2g_payload": False,
        "local_score_context_available_in_stage2g_payload": False,
        "feature_materialization_authorized": False,
        "model_training_started": False,
        "model_selection_started": False,
        "full_train_final_fit_started": False,
        "original_validation_target_access": False,
        "calibration_target_access": False,
        "holdout_target_access": False,
        "function_token_rewrite_used": False,
        "duration_inference_used": False,
        "segment_boundary_inference_used": False,
        "production_authority": False,
        "deterministic_resolver_remains_authoritative": True,
    }
    rendered = json.dumps(summary, sort_keys=True, ensure_ascii=False)
    for private_key in ("phrase_key", "carrier_event_id", "function_token", "source_annotation_sha256"):
        if f'"{private_key}"' in rendered:
            raise Stage2IFunctionEventFeatureAuditError("shareable Stage 2-I summary leaks private event data")
    return summary


def run_stage2i_audit_from_file(stage2g_private_path: str | Path) -> dict[str, object]:
    require_locked_runtime()
    data = load_bounded_json(stage2g_private_path, max_bytes=MAX_PRIVATE_BYTES)
    return run_stage2i_audit(data)


def canonical_stage2i_json(data: dict[str, object]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
