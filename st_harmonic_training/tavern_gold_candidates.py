from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import stat
from typing import Any

from .safe_ingest import load_bounded_json
from .tavern_adjudication import (
    ADJUDICATION_INPUT_SCHEMA,
    DECISIONS,
    PINNED_TAVERN_AB_COMPARISON_SHA256,
)
from .tavern_structure import PINNED_TAVERN_REVISION

GOLD_CANDIDATE_PLAN_SCHEMA = "st-tavern-gold-candidate-plan-v1"
GOLD_CANDIDATE_SUMMARY_SCHEMA = "st-tavern-gold-candidate-mapping-summary-v1"
PINNED_VALIDATED_HUMAN_DECISIONS_SHA256 = (
    "0e53133bf150a101f1b55329c4c5741168fbe7b9ac9a748f221ec07fade1be4a"
)
PINNED_VALIDATED_HUMAN_DECISION_COUNT = 694
MAX_VALIDATED_DECISIONS_BYTES = 1024 * 1024
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

DECISION_TO_DISPOSITION = {
    "SELECT_A": "GOLD_EXPERT_CANDIDATE",
    "SELECT_B": "GOLD_EXPERT_CANDIDATE",
    "PRESERVE_VARIANTS": "GOLD_VARIANT_CANDIDATE",
    "CONFIRM_EQUIVALENT": "GOLD_CONSENSUS_CANDIDATE",
    "AMBIGUOUS": "QUARANTINE_AMBIGUOUS",
    "ABSTAIN": "QUARANTINE_ABSTAIN",
}


class TavernGoldCandidateError(ValueError):
    pass


def _required_text(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TavernGoldCandidateError(f"{key} must be a non-empty string")
    return value.strip()


def _required_sha(data: dict[str, Any], key: str) -> str:
    value = _required_text(data, key)
    if not SHA256_RE.fullmatch(value):
        raise TavernGoldCandidateError(f"{key} must be lowercase SHA-256 hex")
    return value


def _validate_artifact_sha(observed: str, expected: str) -> None:
    if not SHA256_RE.fullmatch(observed) or not SHA256_RE.fullmatch(expected):
        raise TavernGoldCandidateError("artifact SHA-256 must be lowercase hex")
    if observed != expected:
        raise TavernGoldCandidateError(
            f"validated human-decision artifact SHA-256 mismatch: expected {expected}, got {observed}"
        )


def build_tavern_gold_candidate_plan(
    adjudication: object,
    *,
    artifact_sha256: str,
    expected_artifact_sha256: str = PINNED_VALIDATED_HUMAN_DECISIONS_SHA256,
    expected_decision_count: int = PINNED_VALIDATED_HUMAN_DECISION_COUNT,
) -> dict[str, object]:
    _validate_artifact_sha(artifact_sha256, expected_artifact_sha256)
    if not isinstance(expected_decision_count, int) or isinstance(expected_decision_count, bool) or expected_decision_count < 0:
        raise TavernGoldCandidateError("expected_decision_count must be a non-negative integer")
    if not isinstance(adjudication, dict) or adjudication.get("schema_version") != ADJUDICATION_INPUT_SCHEMA:
        raise TavernGoldCandidateError("unsupported validated human-adjudication schema")
    if adjudication.get("source_corpus") != "TAVERN":
        raise TavernGoldCandidateError("adjudication source corpus mismatch")
    if adjudication.get("source_revision") != PINNED_TAVERN_REVISION:
        raise TavernGoldCandidateError("adjudication source revision mismatch")
    if adjudication.get("reviewer_type") != "HUMAN":
        raise TavernGoldCandidateError("validated decisions must come from a human reviewer")
    if adjudication.get("comparison_evidence_sha256") != PINNED_TAVERN_AB_COMPARISON_SHA256:
        raise TavernGoldCandidateError("adjudication comparison evidence SHA-256 mismatch")

    reviewer_ref = _required_text(adjudication, "reviewer_ref")
    review_session_id = _required_text(adjudication, "review_session_id")
    decisions = adjudication.get("decisions")
    if not isinstance(decisions, list) or not all(isinstance(item, dict) for item in decisions):
        raise TavernGoldCandidateError("decisions must be an array of objects")
    if len(decisions) != expected_decision_count:
        raise TavernGoldCandidateError(
            f"validated human-decision count mismatch: expected {expected_decision_count}, got {len(decisions)}"
        )

    seen: set[str] = set()
    candidates: list[dict[str, object]] = []
    decision_counts: Counter[str] = Counter()
    disposition_counts: Counter[str] = Counter()
    for item in decisions:
        phrase_key = _required_text(item, "phrase_key")
        if phrase_key in seen:
            raise TavernGoldCandidateError(f"duplicate validated human decision: {phrase_key}")
        seen.add(phrase_key)
        decision = _required_text(item, "decision")
        if decision not in DECISIONS:
            raise TavernGoldCandidateError(f"unsupported human decision: {decision}")
        a_hash = _required_sha(item, "annotator_A_raw_sha256")
        b_hash = _required_sha(item, "annotator_B_raw_sha256")

        disposition = DECISION_TO_DISPOSITION[decision]
        selected_source: str | None
        if decision == "SELECT_A":
            selected_source = "A"
        elif decision == "SELECT_B":
            selected_source = "B"
        elif decision == "PRESERVE_VARIANTS":
            selected_source = "A+B"
        elif decision == "CONFIRM_EQUIVALENT":
            selected_source = "A+B_HUMAN_CONFIRMED_EQUIVALENT"
        else:
            selected_source = None

        candidates.append({
            "phrase_key": phrase_key,
            "human_decision": decision,
            "candidate_disposition": disposition,
            "selected_source": selected_source,
            "annotator_A_raw_sha256": a_hash,
            "annotator_B_raw_sha256": b_hash,
        })
        decision_counts[decision] += 1
        disposition_counts[disposition] += 1

    candidates.sort(key=lambda item: str(item["phrase_key"]))
    quarantined = sum(
        count for key, count in disposition_counts.items() if key.startswith("QUARANTINE_")
    )
    teacher_gold_candidates = len(candidates) - quarantined

    return {
        "schema_version": GOLD_CANDIDATE_PLAN_SCHEMA,
        "source_corpus": "TAVERN",
        "source_revision": PINNED_TAVERN_REVISION,
        "comparison_evidence_sha256": PINNED_TAVERN_AB_COMPARISON_SHA256,
        "validated_human_decisions_sha256": artifact_sha256,
        "reviewer_ref": reviewer_ref,
        "review_session_id": review_session_id,
        "validated_decision_count": len(candidates),
        "decision_counts": {key: decision_counts[key] for key in sorted(decision_counts)},
        "candidate_disposition_counts": {
            key: disposition_counts[key] for key in sorted(disposition_counts)
        },
        "teacher_gold_candidate_count": teacher_gold_candidates,
        "quarantined_count": quarantined,
        "mapping_status": "CANDIDATE_ONLY_NO_GOLD_RECORDS",
        "candidates": candidates,
        "gold_assignment_authorized": False,
        "partition_assignment_authorized": False,
        "training_authorized": False,
    }


def build_tavern_gold_candidate_plan_from_file(path: str | Path) -> dict[str, object]:
    candidate_path = Path(path)
    if candidate_path.is_symlink():
        raise TavernGoldCandidateError("symlink validated-decision input rejected")
    try:
        metadata = candidate_path.stat()
    except OSError as exc:
        raise TavernGoldCandidateError("cannot stat validated-decision input") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise TavernGoldCandidateError("validated-decision input must be a regular file")
    if metadata.st_size > MAX_VALIDATED_DECISIONS_BYTES:
        raise TavernGoldCandidateError("validated-decision input exceeds bounded size")
    try:
        raw = candidate_path.read_bytes()
    except OSError as exc:
        raise TavernGoldCandidateError("cannot read validated-decision input") from exc
    if len(raw) > MAX_VALIDATED_DECISIONS_BYTES:
        raise TavernGoldCandidateError("validated-decision input exceeds bounded size after read")
    observed_sha256 = hashlib.sha256(raw).hexdigest()
    return build_tavern_gold_candidate_plan(
        load_bounded_json(candidate_path, max_bytes=MAX_VALIDATED_DECISIONS_BYTES),
        artifact_sha256=observed_sha256,
    )


def build_tavern_gold_candidate_summary(plan: object) -> dict[str, object]:
    if not isinstance(plan, dict) or plan.get("schema_version") != GOLD_CANDIDATE_PLAN_SCHEMA:
        raise TavernGoldCandidateError("unsupported TAVERN gold-candidate plan")
    for field in (
        "gold_assignment_authorized",
        "partition_assignment_authorized",
        "training_authorized",
    ):
        if plan.get(field) is not False:
            raise TavernGoldCandidateError(f"gold-candidate plan must keep {field}=false")
    return {
        "schema_version": GOLD_CANDIDATE_SUMMARY_SCHEMA,
        "source_corpus": plan["source_corpus"],
        "source_revision": plan["source_revision"],
        "comparison_evidence_sha256": plan["comparison_evidence_sha256"],
        "validated_human_decisions_sha256": plan["validated_human_decisions_sha256"],
        "validated_decision_count": plan["validated_decision_count"],
        "decision_counts": plan["decision_counts"],
        "candidate_disposition_counts": plan["candidate_disposition_counts"],
        "teacher_gold_candidate_count": plan["teacher_gold_candidate_count"],
        "quarantined_count": plan["quarantined_count"],
        "mapping_status": plan["mapping_status"],
        "gold_assignment_authorized": False,
        "partition_assignment_authorized": False,
        "training_authorized": False,
    }


def canonical_tavern_gold_candidate_json(data: dict[str, object]) -> str:
    if data.get("schema_version") not in {GOLD_CANDIDATE_PLAN_SCHEMA, GOLD_CANDIDATE_SUMMARY_SCHEMA}:
        raise TavernGoldCandidateError("unsupported TAVERN gold-candidate schema")
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
