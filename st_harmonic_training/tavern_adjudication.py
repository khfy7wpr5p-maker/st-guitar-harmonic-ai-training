from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .safe_ingest import load_bounded_json
from .tavern_ab_compare import COMPARISON_SCHEMA, canonical_ab_comparison_json
from .tavern_structure import PINNED_TAVERN_REVISION

ADJUDICATION_INPUT_SCHEMA = "st-tavern-human-adjudication-v1"
ADJUDICATION_GATE_SCHEMA = "st-tavern-adjudication-gate-v1"
PINNED_TAVERN_AB_COMPARISON_SHA256 = (
    "b6f3e80c98acbdeac964ae47f568bf9a6c7eead6efbc221b47d74cdb56293db4"
)
PINNED_TAVERN_AB_PAIR_COUNT = 937
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

DECISIONS = frozenset({
    "CONFIRM_EQUIVALENT",
    "SELECT_A",
    "SELECT_B",
    "PRESERVE_VARIANTS",
    "AMBIGUOUS",
    "ABSTAIN",
})
EQUIVALENT_RELATIONS = frozenset({"BYTE_EXACT", "TEXT_LINE_ENDING_EQUIVALENT"})
ALLOWED_RELATIONS = frozenset({
    "BYTE_EXACT",
    "TEXT_LINE_ENDING_EQUIVALENT",
    "TEXT_DIFFERENT",
})


class TavernAdjudicationError(ValueError):
    pass


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _required_text(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TavernAdjudicationError(f"{key} must be a non-empty string")
    return value.strip()


def _required_sha(data: dict[str, Any], key: str) -> str:
    value = _required_text(data, key)
    if not SHA256_RE.fullmatch(value):
        raise TavernAdjudicationError(f"{key} must be lowercase SHA-256 hex")
    return value


def _validate_expected_sha(value: str) -> str:
    normalized = value.strip().lower()
    if not SHA256_RE.fullmatch(normalized):
        raise TavernAdjudicationError("expected comparison SHA-256 must be lowercase hex")
    return normalized


def _validate_comparison(
    data: object,
    *,
    expected_comparison_sha256: str,
    expected_pair_count: int | None,
) -> tuple[dict[str, dict[str, Any]], str]:
    if not isinstance(data, dict) or data.get("schema_version") != COMPARISON_SCHEMA:
        raise TavernAdjudicationError("unsupported TAVERN A/B comparison evidence")
    if data.get("source_corpus") != "TAVERN":
        raise TavernAdjudicationError("comparison source corpus mismatch")
    if data.get("source_revision") != PINNED_TAVERN_REVISION:
        raise TavernAdjudicationError("comparison source revision mismatch")
    if data.get("comparison_scope") != "EVIDENCE_ONLY_NO_SEMANTIC_EQUIVALENCE":
        raise TavernAdjudicationError("comparison scope is not admissible")
    for field in (
        "adjudication_authorized",
        "gold_assignment_authorized",
        "partition_assignment_authorized",
        "training_authorized",
    ):
        if data.get(field) is not False:
            raise TavernAdjudicationError(f"comparison evidence must keep {field}=false")

    comparisons = data.get("comparisons")
    pair_count = data.get("pair_count")
    if not isinstance(comparisons, list) or not all(isinstance(item, dict) for item in comparisons):
        raise TavernAdjudicationError("comparisons must be an array of objects")
    if not isinstance(pair_count, int) or pair_count < 0 or len(comparisons) != pair_count:
        raise TavernAdjudicationError("comparison pair_count mismatch")
    if expected_pair_count is not None and pair_count != expected_pair_count:
        raise TavernAdjudicationError(
            f"comparison pair_count is not pinned evidence: expected {expected_pair_count}, got {pair_count}"
        )

    by_phrase: dict[str, dict[str, Any]] = {}
    relation_counts: Counter[str] = Counter()
    for record in comparisons:
        phrase_key = _required_text(record, "phrase_key")
        if phrase_key in by_phrase:
            raise TavernAdjudicationError(f"duplicate comparison phrase_key: {phrase_key}")
        relation = _required_text(record, "relation")
        if relation not in ALLOWED_RELATIONS:
            raise TavernAdjudicationError(f"unsupported comparison relation: {relation}")
        for key in (
            "annotator_A_raw_sha256",
            "annotator_B_raw_sha256",
            "annotator_A_canonical_text_sha256",
            "annotator_B_canonical_text_sha256",
        ):
            _required_sha(record, key)
        by_phrase[phrase_key] = record
        relation_counts[relation] += 1

    declared_counts = data.get("relation_counts")
    if not isinstance(declared_counts, dict) or dict(sorted(relation_counts.items())) != declared_counts:
        raise TavernAdjudicationError("comparison relation_counts mismatch")

    canonical = canonical_ab_comparison_json(data)
    comparison_sha256 = _sha256_text(canonical)
    if comparison_sha256 != expected_comparison_sha256:
        raise TavernAdjudicationError(
            "comparison evidence SHA-256 mismatch: "
            f"expected {expected_comparison_sha256}, observed {comparison_sha256}"
        )
    return by_phrase, comparison_sha256


def _validate_human_input(
    data: object,
    comparison_by_phrase: dict[str, dict[str, Any]],
    comparison_sha256: str,
) -> tuple[str, str, list[dict[str, Any]]]:
    if not isinstance(data, dict) or data.get("schema_version") != ADJUDICATION_INPUT_SCHEMA:
        raise TavernAdjudicationError("unsupported human adjudication schema")
    if data.get("source_corpus") != "TAVERN":
        raise TavernAdjudicationError("adjudication source corpus mismatch")
    if data.get("source_revision") != PINNED_TAVERN_REVISION:
        raise TavernAdjudicationError("adjudication source revision mismatch")
    if data.get("reviewer_type") != "HUMAN":
        raise TavernAdjudicationError("adjudication decisions must come from a human reviewer")

    reviewer_ref = _required_text(data, "reviewer_ref")
    review_session_id = _required_text(data, "review_session_id")
    if _required_sha(data, "comparison_evidence_sha256") != comparison_sha256:
        raise TavernAdjudicationError("human adjudication is not bound to this comparison evidence")

    decisions = data.get("decisions")
    if not isinstance(decisions, list) or not all(isinstance(item, dict) for item in decisions):
        raise TavernAdjudicationError("decisions must be an array of objects")

    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for item in decisions:
        phrase_key = _required_text(item, "phrase_key")
        if phrase_key in seen:
            raise TavernAdjudicationError(f"duplicate human decision: {phrase_key}")
        seen.add(phrase_key)
        comparison = comparison_by_phrase.get(phrase_key)
        if comparison is None:
            raise TavernAdjudicationError(f"human decision references unknown phrase: {phrase_key}")

        a_hash = _required_sha(item, "annotator_A_raw_sha256")
        b_hash = _required_sha(item, "annotator_B_raw_sha256")
        if a_hash != comparison["annotator_A_raw_sha256"] or b_hash != comparison["annotator_B_raw_sha256"]:
            raise TavernAdjudicationError(f"human decision hash anchor mismatch: {phrase_key}")

        decision = _required_text(item, "decision")
        if decision not in DECISIONS:
            raise TavernAdjudicationError(f"unsupported human decision: {decision}")
        relation = comparison["relation"]
        if decision == "CONFIRM_EQUIVALENT" and relation not in EQUIVALENT_RELATIONS:
            raise TavernAdjudicationError(
                f"cannot confirm textual equivalence for TEXT_DIFFERENT phrase: {phrase_key}"
            )
        if decision in {"SELECT_A", "SELECT_B"} and relation != "TEXT_DIFFERENT":
            raise TavernAdjudicationError(
                f"source selection is only valid for TEXT_DIFFERENT phrase: {phrase_key}"
            )

        normalized.append({
            "phrase_key": phrase_key,
            "decision": decision,
            "comparison_relation": relation,
            "annotator_A_raw_sha256": a_hash,
            "annotator_B_raw_sha256": b_hash,
        })

    return reviewer_ref, review_session_id, sorted(normalized, key=lambda item: item["phrase_key"])


def build_tavern_adjudication_gate(
    comparison_evidence: object,
    human_adjudication: object,
    *,
    expected_comparison_sha256: str = PINNED_TAVERN_AB_COMPARISON_SHA256,
    expected_pair_count: int | None = PINNED_TAVERN_AB_PAIR_COUNT,
) -> dict[str, object]:
    expected_sha = _validate_expected_sha(expected_comparison_sha256)
    if expected_pair_count is not None and (
        not isinstance(expected_pair_count, int) or expected_pair_count < 0
    ):
        raise TavernAdjudicationError("expected_pair_count must be non-negative integer or null")

    comparison_by_phrase, comparison_sha256 = _validate_comparison(
        comparison_evidence,
        expected_comparison_sha256=expected_sha,
        expected_pair_count=expected_pair_count,
    )
    reviewer_ref, review_session_id, decisions = _validate_human_input(
        human_adjudication,
        comparison_by_phrase,
        comparison_sha256,
    )

    decision_counts = Counter(item["decision"] for item in decisions)
    relation_review_counts = Counter(item["comparison_relation"] for item in decisions)
    reviewed = len(decisions)
    total = len(comparison_by_phrase)
    pending = total - reviewed

    return {
        "schema_version": ADJUDICATION_GATE_SCHEMA,
        "source_corpus": "TAVERN",
        "source_revision": PINNED_TAVERN_REVISION,
        "comparison_evidence_sha256": comparison_sha256,
        "review_session_id": review_session_id,
        "reviewer_ref": reviewer_ref,
        "reviewer_type": "HUMAN",
        "total_pair_count": total,
        "reviewed_count": reviewed,
        "pending_count": pending,
        "review_status": "COMPLETE" if pending == 0 else "INCOMPLETE",
        "decision_counts": {
            key: decision_counts[key] for key in sorted(decision_counts)
        },
        "reviewed_relation_counts": {
            key: relation_review_counts[key] for key in sorted(relation_review_counts)
        },
        "decisions": decisions,
        "gold_assignment_authorized": False,
        "partition_assignment_authorized": False,
        "training_authorized": False,
    }


def build_tavern_adjudication_gate_from_files(
    comparison_path: str | Path,
    human_adjudication_path: str | Path,
) -> dict[str, object]:
    return build_tavern_adjudication_gate(
        load_bounded_json(comparison_path),
        load_bounded_json(human_adjudication_path),
    )


def canonical_adjudication_gate_json(evidence: dict[str, object]) -> str:
    if evidence.get("schema_version") != ADJUDICATION_GATE_SCHEMA:
        raise TavernAdjudicationError("unsupported TAVERN adjudication gate schema")
    return json.dumps(
        evidence,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ) + "\n"
