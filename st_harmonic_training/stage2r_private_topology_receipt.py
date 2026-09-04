"""Aggregate-only private receipt for Stage 2-R dynamic spine topology."""
from __future__ import annotations

import json

RECEIPT_SCHEMA = "st-stage2r-private-dynamic-spine-topology-receipt-v1"
SOURCE_TRAINING_MAIN_SHA = "51ea94008514889f4fe41c881d9c3c02f3d61ce0"
SOURCE_STAGE2G_MANIFEST = "d7bbd514ec85b87aee423cae9dce39c74e634ab2f1040fed82af0e25105f255d"
SOURCE_TAVERN_SHA256 = "b95d85bb3f1e5c0f4ea6df772928d247243485abd93153f0550d6be2fba4fc63"


class Stage2RPrivateTopologyReceiptError(ValueError):
    pass


def expected_receipt() -> dict[str, object]:
    return {
        "schema_version": RECEIPT_SCHEMA,
        "source_training_main_sha": SOURCE_TRAINING_MAIN_SHA,
        "source_stage2g_private_event_manifest_sha256": SOURCE_STAGE2G_MANIFEST,
        "source_tavern_archive_sha256": SOURCE_TAVERN_SHA256,
        "private_audit_execution_mode": "PRIVATE_RAW_STRUCTURE_SCAN_EQUIVALENT_TO_STAGE2R_CONTRACT",
        "merged_stage2r_runner_reexecution_completed": False,
        "source_path_count": 363,
        "materialized_event_count": 1854,
        "score_dynamic_source_path_count": 99,
        "joined_dynamic_source_path_count": 120,
        "dynamic_union_source_path_count": 128,
        "dynamic_intersection_source_path_count": 91,
        "score_only_dynamic_source_path_count": 8,
        "joined_only_dynamic_source_path_count": 29,
        "score_operation_path_counts": {"*^": 99, "*v": 98, "*x": 0, "*+": 0},
        "joined_operation_path_counts": {"*^": 120, "*v": 120, "*x": 0, "*+": 0},
        "score_operation_occurrence_counts": {"*^": 145, "*v": 286, "*x": 0, "*+": 0},
        "joined_operation_occurrence_counts": {"*^": 184, "*v": 368, "*x": 0, "*+": 0},
        "score_initial_kern_spine_count_histogram": {"2": 314, "4": 49},
        "joined_initial_kern_spine_count_histogram": {"2": 363},
        "score_max_observed_kern_spine_count_histogram": {"2": 215, "3": 89, "4": 59},
        "joined_max_observed_kern_spine_count_histogram": {"2": 243, "3": 98, "4": 21, "5": 1},
        "exchange_or_add_observed": False,
        "split_join_only_dynamic_topology_observed": True,
        "dynamic_spine_materialization_authorized": False,
        "timing_inference_authorized": False,
        "model_feature_materialization_authorized": False,
        "model_training_started": False,
        "non_train_access": False,
        "production_authority": False,
        "deterministic_resolver_remains_authoritative": True,
        "decision": "SPLIT_JOIN_TOPOLOGY_BOUNDED_DESIGN_EXACT_LINEAGE_MATERIALIZER_NEXT",
    }


def validate_receipt(data: object) -> dict[str, object]:
    expected = expected_receipt()
    if not isinstance(data, dict) or data != expected:
        raise Stage2RPrivateTopologyReceiptError("Stage 2-R private topology receipt differs from frozen aggregate evidence")
    if int(data["dynamic_union_source_path_count"]) != (
        int(data["dynamic_intersection_source_path_count"])
        + int(data["score_only_dynamic_source_path_count"])
        + int(data["joined_only_dynamic_source_path_count"])
    ):
        raise Stage2RPrivateTopologyReceiptError("dynamic union decomposition does not close")
    if sum(int(v) for v in dict(data["score_initial_kern_spine_count_histogram"]).values()) != 363:
        raise Stage2RPrivateTopologyReceiptError("score initial-spine histogram does not close")
    if sum(int(v) for v in dict(data["joined_initial_kern_spine_count_histogram"]).values()) != 363:
        raise Stage2RPrivateTopologyReceiptError("Joined initial-spine histogram does not close")
    if sum(int(v) for v in dict(data["score_max_observed_kern_spine_count_histogram"]).values()) != 363:
        raise Stage2RPrivateTopologyReceiptError("score max-spine histogram does not close")
    if sum(int(v) for v in dict(data["joined_max_observed_kern_spine_count_histogram"]).values()) != 363:
        raise Stage2RPrivateTopologyReceiptError("Joined max-spine histogram does not close")
    rendered = json.dumps(data, sort_keys=True, ensure_ascii=False)
    for forbidden in ("phrase_key", "function_token", "carrier_event_id", "source_annotation_sha256"):
        if f'"{forbidden}"' in rendered:
            raise Stage2RPrivateTopologyReceiptError("Stage 2-R receipt leaks private event data")
    return data
