from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .safe_ingest import load_bounded_json
from .tavern_lineage import LINEAGE_SCHEMA
from .tavern_structure import PINNED_TAVERN_REVISION, STRUCTURE_SCHEMA

PHRASE_GATE_SCHEMA = "st-tavern-phrase-gate-v1"

ALLOWED_STATUSES = frozenset({
    "PAIR_COMPLETE",
    "SCORE_B_ONLY",
    "SCORE_ONLY",
    "ANALYSIS_WITHOUT_SCORE",
    "DERIVED_OR_UNDOCUMENTED_ONLY",
})


class TavernPhraseGateError(ValueError):
    pass


def _required_count(mapping: dict[str, Any], key: str) -> int:
    value = mapping.get(key, 0)
    if not isinstance(value, int) or value < 0:
        raise TavernPhraseGateError(f"{key} must be a non-negative integer")
    return value


def _validate_inputs(structure: object, lineage: object) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(structure, dict) or structure.get("schema_version") != STRUCTURE_SCHEMA:
        raise TavernPhraseGateError("unsupported TAVERN structure evidence")
    if structure.get("immutable_revision") != PINNED_TAVERN_REVISION:
        raise TavernPhraseGateError("TAVERN structure revision mismatch")
    if structure.get("training_authorized") is not False:
        raise TavernPhraseGateError("structure evidence must not authorize training")

    if not isinstance(lineage, dict) or lineage.get("schema_version") != LINEAGE_SCHEMA:
        raise TavernPhraseGateError("unsupported TAVERN lineage evidence")
    if lineage.get("source_revision") != PINNED_TAVERN_REVISION:
        raise TavernPhraseGateError("TAVERN lineage revision mismatch")
    if lineage.get("partition_assignment_authorized") is not False:
        raise TavernPhraseGateError("lineage evidence must not authorize partition assignment")
    if lineage.get("training_authorized") is not False:
        raise TavernPhraseGateError("lineage evidence must not authorize training")
    if lineage.get("work_family_count") != 27:
        raise TavernPhraseGateError("lineage evidence must contain exactly 27 work families")

    counts = structure.get("phrase_status_counts")
    if not isinstance(counts, dict):
        raise TavernPhraseGateError("phrase_status_counts must be an object")
    unknown = sorted(set(counts) - ALLOWED_STATUSES)
    if unknown:
        raise TavernPhraseGateError("unknown phrase status: " + ",".join(unknown))

    observed = structure.get("observed_counts")
    if not isinstance(observed, dict):
        raise TavernPhraseGateError("observed_counts must be an object")
    phrase_keys = _required_count(observed, "phrase_keys")
    total = sum(_required_count(counts, status) for status in ALLOWED_STATUSES)
    if total != phrase_keys:
        raise TavernPhraseGateError(
            f"phrase status total mismatch: statuses={total}, phrase_keys={phrase_keys}"
        )
    return structure, lineage


def build_tavern_phrase_gate(structure: object, lineage: object) -> dict[str, object]:
    structure_data, lineage_data = _validate_inputs(structure, lineage)
    counts = structure_data["phrase_status_counts"]

    pair_complete = _required_count(counts, "PAIR_COMPLETE")
    score_b_only = _required_count(counts, "SCORE_B_ONLY")
    score_only = _required_count(counts, "SCORE_ONLY")
    analysis_without_score = _required_count(counts, "ANALYSIS_WITHOUT_SCORE")
    derived_or_undocumented = _required_count(counts, "DERIVED_OR_UNDOCUMENTED_ONLY")

    return {
        "schema_version": PHRASE_GATE_SCHEMA,
        "source_corpus": "TAVERN",
        "source_revision": PINNED_TAVERN_REVISION,
        "lineage_work_family_count": lineage_data["work_family_count"],
        "observed_phrase_count": sum((
            pair_complete,
            score_b_only,
            score_only,
            analysis_without_score,
            derived_or_undocumented,
        )),
        "queues": {
            "human_pair_adjudication": {
                "count": pair_complete,
                "source_status": "PAIR_COMPLETE",
                "decision": "A_B_CONTENT_COMPARISON_REQUIRED",
                "gold_tier_assigned": None,
            },
            "single_human_review": {
                "count": score_b_only,
                "source_status": "SCORE_B_ONLY",
                "decision": "SINGLE_HUMAN_PROVENANCE_REVIEW_REQUIRED",
                "gold_tier_assigned": None,
            },
            "blocked_missing_annotation": {
                "count": score_only,
                "source_status": "SCORE_ONLY",
                "decision": "NO_HUMAN_ANALYSIS_AVAILABLE",
                "gold_tier_assigned": None,
            },
            "blocked_missing_score": {
                "count": analysis_without_score,
                "source_status": "ANALYSIS_WITHOUT_SCORE",
                "decision": "MISSING_SCORE",
                "gold_tier_assigned": None,
            },
            "quarantine_undocumented_or_derived": {
                "count": derived_or_undocumented,
                "source_status": "DERIVED_OR_UNDOCUMENTED_ONLY",
                "decision": "QUARANTINE",
                "gold_tier_assigned": None,
            },
        },
        "teacher_gold_candidate_count": pair_complete,
        "single_human_review_candidate_count": score_b_only,
        "hard_blocked_phrase_count": score_only + analysis_without_score + derived_or_undocumented,
        "remaining_blockers": [
            "DECLARED_1060_VS_OBSERVED_1129_UNRESOLVED",
            "A_B_CONTENT_COMPARISON_REQUIRED",
            "SINGLE_HUMAN_PROVENANCE_REVIEW_REQUIRED",
            "UNDOCUMENTED_ENCODER_C_REMAINS_QUARANTINED",
        ],
        "gold_assignment_authorized": False,
        "partition_assignment_authorized": False,
        "training_authorized": False,
    }


def build_tavern_phrase_gate_from_files(
    structure_path: str | Path,
    lineage_path: str | Path,
) -> dict[str, object]:
    return build_tavern_phrase_gate(
        load_bounded_json(structure_path),
        load_bounded_json(lineage_path),
    )


def canonical_phrase_gate_json(evidence: dict[str, object]) -> str:
    if evidence.get("schema_version") != PHRASE_GATE_SCHEMA:
        raise TavernPhraseGateError("unsupported TAVERN phrase gate schema")
    return json.dumps(
        evidence,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ) + "\n"
