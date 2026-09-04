"""Bounded aggregate receipt for the private Stage 2-Q v2 corpus audit.

The receipt contains no phrase identities, targets, carrier ids, or annotation
hashes beyond already-frozen public manifest pins. It records aggregate evidence
only and cannot authorize model training or production authority.
"""
from __future__ import annotations

import json
from pathlib import Path

RECEIPT_SCHEMA = "st-stage2q-private-exact-alignment-receipt-v1"
SOURCE_STAGE2Q_V2_MAIN_SHA = "fa48249217e8014de3ac331b8f4b611d2d374b95"
SOURCE_STAGE2G_MANIFEST = "d7bbd514ec85b87aee423cae9dce39c74e634ab2f1040fed82af0e25105f255d"
SOURCE_TAVERN_ARCHIVE_SHA256 = "b95d85bb3f1e5c0f4ea6df772928d247243485abd93153f0550d6be2fba4fc63"
EXPECTED_SOURCE_PATH_COUNT = 363
EXPECTED_EVENT_COUNT = 1854


class Stage2QPrivateCoverageReceiptError(ValueError):
    pass


def expected_receipt() -> dict[str, object]:
    return {
        "schema_version": RECEIPT_SCHEMA,
        "source_stage2q_v2_main_sha": SOURCE_STAGE2Q_V2_MAIN_SHA,
        "source_stage2g_private_event_manifest_sha256": SOURCE_STAGE2G_MANIFEST,
        "source_tavern_archive_sha256": SOURCE_TAVERN_ARCHIVE_SHA256,
        "private_audit_execution_mode": "OFFLINE_EQUIVALENT_TO_STAGE2Q_V2_SEMANTICS",
        "merged_stage2q_v2_runner_reexecution_completed": False,
        "source_path_count": 363,
        "materialized_event_count": 1854,
        "score_materializer_supported_source_path_count": 235,
        "joined_exact_timing_supported_source_path_count": 163,
        "score_joined_frame_equivalent_source_path_count": 139,
        "fully_exact_aligned_source_path_count": 137,
        "exact_aligned_event_count": 546,
        "unaligned_event_count": 1308,
        "exact_event_alignment_coverage": 0.294498381877,
        "exact_source_path_alignment_coverage": 0.37741046832,
        "fold_exact_aligned_event_distribution": {"0": 199, "1": 320, "2": 27},
        "source_exact_aligned_event_distribution": {"A": 16, "B": 530},
        "path_failure_reason_counts": {
            "EVENT_LEVEL_EXACT_JOIN_INCOMPLETE": 2,
            "JOINED_EXACT_TIMING_UNSUPPORTED": 72,
            "SCORE_JOINED_FRAME_MISMATCH": 24,
            "SCORE_STAGE2P_UNSUPPORTED": 128,
        },
        "exact_stage2g_event_to_runtime_frame_alignment_complete": False,
        "partial_alignment_auto_admission_authorized": False,
        "model_feature_materialization_authorized": False,
        "model_training_started": False,
        "model_selection_started": False,
        "full_train_final_fit_started": False,
        "non_train_access": False,
        "production_authority": False,
        "deterministic_resolver_remains_authoritative": True,
        "decision": "HOLD_PARTIAL_EXACT_ALIGNMENT_COVERAGE",
    }


def validate_receipt(data: object) -> dict[str, object]:
    expected = expected_receipt()
    if not isinstance(data, dict) or data != expected:
        raise Stage2QPrivateCoverageReceiptError("Stage 2-Q private receipt differs from frozen aggregate evidence")
    if data["source_path_count"] != EXPECTED_SOURCE_PATH_COUNT:
        raise Stage2QPrivateCoverageReceiptError("source-path count mismatch")
    if data["materialized_event_count"] != EXPECTED_EVENT_COUNT:
        raise Stage2QPrivateCoverageReceiptError("event count mismatch")
    if int(data["exact_aligned_event_count"]) + int(data["unaligned_event_count"]) != EXPECTED_EVENT_COUNT:
        raise Stage2QPrivateCoverageReceiptError("aligned/unaligned event totals do not close")
    if sum(int(value) for value in dict(data["fold_exact_aligned_event_distribution"]).values()) != int(data["exact_aligned_event_count"]):
        raise Stage2QPrivateCoverageReceiptError("fold aligned-event totals do not close")
    if sum(int(value) for value in dict(data["source_exact_aligned_event_distribution"]).values()) != int(data["exact_aligned_event_count"]):
        raise Stage2QPrivateCoverageReceiptError("source aligned-event totals do not close")
    if sum(int(value) for value in dict(data["path_failure_reason_counts"]).values()) + int(data["fully_exact_aligned_source_path_count"]) != EXPECTED_SOURCE_PATH_COUNT:
        raise Stage2QPrivateCoverageReceiptError("path outcome totals do not close")
    rendered = json.dumps(data, sort_keys=True, ensure_ascii=False)
    for forbidden in ("phrase_key", "function_token", "carrier_event_id", "source_annotation_sha256"):
        if f'"{forbidden}"' in rendered:
            raise Stage2QPrivateCoverageReceiptError("private receipt leaks event-level identity or target data")
    return data


def load_receipt(path: str | Path) -> dict[str, object]:
    raw = Path(path).read_bytes()
    if len(raw) > 64 * 1024:
        raise Stage2QPrivateCoverageReceiptError("receipt exceeds size bound")
    try:
        data = json.loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Stage2QPrivateCoverageReceiptError("invalid receipt JSON") from exc
    return validate_receipt(data)
