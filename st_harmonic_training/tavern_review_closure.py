from __future__ import annotations

from collections import Counter
import json
import re
from typing import Any

from .tavern_adjudication import PINNED_TAVERN_AB_COMPARISON_SHA256
from .tavern_structure import PINNED_TAVERN_REVISION

CLOSURE_SUMMARY_SCHEMA = "st-tavern-human-review-closure-summary-v1"
RESOLUTION_PLAN_SCHEMA = "st-tavern-human-review-resolution-plan-v1"
PINNED_TAVERN_REVIEW_PAIR_COUNT = 937
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

PERSISTED_DECISIONS = frozenset({
    "SELECT_A",
    "SELECT_B",
    "PRESERVE_VARIANTS",
    "AMBIGUOUS",
    "ABSTAIN",
    "CONFIRM_EQUIVALENT",
})
CONTRACT_STATUSES = frozenset({
    "VALID_STAGE0M_HUMAN_DECISION",
    "USER_ATTESTED_REVIEWED_BUT_VALUE_NOT_PERSISTED",
    "CAPTURED_HUMAN_CHOICE_SCHEMA_INCOMPATIBLE_EQUIVALENT_PAIR",
})
REQUIRED_ARTIFACT_HASHES = frozenset({
    "part1_pdf_sha256",
    "part2_pdf_sha256",
    "closure_json_sha256",
    "validated_decisions_json_sha256",
    "bundle_zip_sha256",
})


class TavernReviewClosureError(ValueError):
    pass


def _required_text(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TavernReviewClosureError(f"{key} must be a non-empty string")
    return value.strip()


def _required_nonnegative_int(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise TavernReviewClosureError(f"{key} must be a non-negative integer")
    return value


def _validate_count_map(
    value: object,
    *,
    field: str,
    allowed_keys: frozenset[str],
) -> dict[str, int]:
    if not isinstance(value, dict):
        raise TavernReviewClosureError(f"{field} must be an object")
    normalized: dict[str, int] = {}
    for key, count in value.items():
        if key not in allowed_keys:
            raise TavernReviewClosureError(f"unsupported {field} key: {key}")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise TavernReviewClosureError(f"{field}.{key} must be a non-negative integer")
        normalized[key] = count
    return dict(sorted(normalized.items()))


def _validate_artifact_hashes(value: object) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != REQUIRED_ARTIFACT_HASHES:
        raise TavernReviewClosureError(
            "artifact_hashes must contain exactly the required summary artifact keys"
        )
    normalized: dict[str, str] = {}
    for key in sorted(REQUIRED_ARTIFACT_HASHES):
        digest = value.get(key)
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            raise TavernReviewClosureError(f"artifact_hashes.{key} must be lowercase SHA-256 hex")
        normalized[key] = digest
    return normalized


def validate_tavern_review_closure_summary(
    data: object,
    *,
    expected_total_pair_count: int = PINNED_TAVERN_REVIEW_PAIR_COUNT,
    expected_comparison_sha256: str = PINNED_TAVERN_AB_COMPARISON_SHA256,
) -> dict[str, object]:
    if not isinstance(data, dict) or data.get("schema_version") != CLOSURE_SUMMARY_SCHEMA:
        raise TavernReviewClosureError("unsupported TAVERN human-review closure summary")
    if data.get("source_corpus") != "TAVERN":
        raise TavernReviewClosureError("closure source corpus mismatch")
    if data.get("source_revision") != PINNED_TAVERN_REVISION:
        raise TavernReviewClosureError("closure source revision mismatch")
    if data.get("comparison_evidence_sha256") != expected_comparison_sha256:
        raise TavernReviewClosureError("closure comparison evidence SHA-256 mismatch")
    if data.get("manual_review_collection_status") != "CLOSED_WITH_PDF_CAPTURE_LOSS":
        raise TavernReviewClosureError("closure status must preserve PDF capture loss")

    for field in (
        "gold_assignment_authorized",
        "partition_assignment_authorized",
        "training_authorized",
    ):
        if data.get(field) is not False:
            raise TavernReviewClosureError(f"closure summary must keep {field}=false")

    if data.get("all_records_reviewed_by_human") is not True:
        raise TavernReviewClosureError("closure must explicitly attest all records were human-reviewed")
    if data.get("manual_refill_required") is not False:
        raise TavernReviewClosureError("closure must explicitly keep manual_refill_required=false")

    total = _required_nonnegative_int(data, "total_pair_count")
    persisted = _required_nonnegative_int(data, "persisted_human_decision_count")
    valid = _required_nonnegative_int(data, "stage0m_valid_human_decision_count")
    capture_loss = _required_nonnegative_int(data, "value_not_persisted_count")
    incompatible = _required_nonnegative_int(data, "schema_incompatible_captured_choice_count")

    if total != expected_total_pair_count:
        raise TavernReviewClosureError(
            f"closure total_pair_count mismatch: expected {expected_total_pair_count}, got {total}"
        )
    if persisted + capture_loss != total:
        raise TavernReviewClosureError("persisted + capture-loss counts must equal total")
    if valid + incompatible != persisted:
        raise TavernReviewClosureError("valid + schema-incompatible counts must equal persisted")

    decision_counts = _validate_count_map(
        data.get("captured_decision_counts"),
        field="captured_decision_counts",
        allowed_keys=PERSISTED_DECISIONS,
    )
    status_counts = _validate_count_map(
        data.get("contract_status_counts"),
        field="contract_status_counts",
        allowed_keys=CONTRACT_STATUSES,
    )
    if sum(decision_counts.values()) != persisted:
        raise TavernReviewClosureError("captured_decision_counts total mismatch")
    expected_status_counts = {
        "CAPTURED_HUMAN_CHOICE_SCHEMA_INCOMPATIBLE_EQUIVALENT_PAIR": incompatible,
        "USER_ATTESTED_REVIEWED_BUT_VALUE_NOT_PERSISTED": capture_loss,
        "VALID_STAGE0M_HUMAN_DECISION": valid,
    }
    if status_counts != dict(sorted(expected_status_counts.items())):
        raise TavernReviewClosureError("contract_status_counts mismatch")

    artifact_hashes = _validate_artifact_hashes(data.get("artifact_hashes"))
    reviewer_ref = _required_text(data, "reviewer_ref")

    return {
        "schema_version": CLOSURE_SUMMARY_SCHEMA,
        "source_corpus": "TAVERN",
        "source_revision": PINNED_TAVERN_REVISION,
        "comparison_evidence_sha256": expected_comparison_sha256,
        "reviewer_ref": reviewer_ref,
        "all_records_reviewed_by_human": True,
        "manual_refill_required": False,
        "manual_review_collection_status": "CLOSED_WITH_PDF_CAPTURE_LOSS",
        "total_pair_count": total,
        "persisted_human_decision_count": persisted,
        "stage0m_valid_human_decision_count": valid,
        "value_not_persisted_count": capture_loss,
        "schema_incompatible_captured_choice_count": incompatible,
        "captured_decision_counts": decision_counts,
        "contract_status_counts": status_counts,
        "artifact_hashes": artifact_hashes,
        "gold_assignment_authorized": False,
        "partition_assignment_authorized": False,
        "training_authorized": False,
    }


def build_tavern_review_resolution_plan(
    closure_summary: object,
    *,
    expected_total_pair_count: int = PINNED_TAVERN_REVIEW_PAIR_COUNT,
    expected_comparison_sha256: str = PINNED_TAVERN_AB_COMPARISON_SHA256,
) -> dict[str, object]:
    summary = validate_tavern_review_closure_summary(
        closure_summary,
        expected_total_pair_count=expected_total_pair_count,
        expected_comparison_sha256=expected_comparison_sha256,
    )
    valid = int(summary["stage0m_valid_human_decision_count"])
    capture_loss = int(summary["value_not_persisted_count"])
    incompatible = int(summary["schema_incompatible_captured_choice_count"])

    disposition_counts = {
        "ADMISSIBLE_STAGE0M_HUMAN_INPUT": valid,
        "QUARANTINE_PDF_CAPTURE_LOSS": capture_loss,
        "QUARANTINE_SCHEMA_INCOMPATIBLE_CHOICE": incompatible,
    }
    return {
        "schema_version": RESOLUTION_PLAN_SCHEMA,
        "source_corpus": "TAVERN",
        "source_revision": PINNED_TAVERN_REVISION,
        "comparison_evidence_sha256": expected_comparison_sha256,
        "total_pair_count": int(summary["total_pair_count"]),
        "manual_review_collection_status": summary["manual_review_collection_status"],
        "disposition_counts": disposition_counts,
        "eligible_for_gold_mapping_count": valid,
        "quarantined_count": capture_loss + incompatible,
        "gold_mapping_status": "CANDIDATE_INPUT_ONLY",
        "capture_loss_policy": "QUARANTINE_NO_INFERENCE_NO_REFILL",
        "schema_incompatible_policy": "QUARANTINE_NO_AUTOMATIC_EQUIVALENCE_PROMOTION",
        "gold_assignment_authorized": False,
        "partition_assignment_authorized": False,
        "training_authorized": False,
    }


def canonical_tavern_review_resolution_plan_json(plan: dict[str, object]) -> str:
    if plan.get("schema_version") != RESOLUTION_PLAN_SCHEMA:
        raise TavernReviewClosureError("unsupported TAVERN review resolution plan schema")
    return json.dumps(plan, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
