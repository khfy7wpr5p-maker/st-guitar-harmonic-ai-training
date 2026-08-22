from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import stat
from typing import Any

from .contracts import AdjudicationOutcome, AnnotationKind, GoldRecord, GoldTier
from .normalization import NORMALIZATION_VERSION
from .safe_ingest import load_bounded_json
from .tavern_adjudication import ADJUDICATION_INPUT_SCHEMA, PINNED_TAVERN_AB_COMPARISON_SHA256
from .tavern_structure import PINNED_TAVERN_REVISION

MATERIALIZATION_SCHEMA = "st-tavern-gold-materialization-v1"
SUMMARY_SCHEMA = "st-tavern-gold-materialization-summary-v1"
PINNED_VALIDATED_SHA256 = "0e53133bf150a101f1b55329c4c5741168fbe7b9ac9a748f221ec07fade1be4a"
PINNED_COUNT = 694
MAX_INPUT_BYTES = 1024 * 1024
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class TavernGoldMaterializationError(ValueError):
    pass


def _text(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TavernGoldMaterializationError(f"{key} must be a non-empty string")
    return value.strip()


def _sha(data: dict[str, Any], key: str) -> str:
    value = _text(data, key)
    if not SHA256_RE.fullmatch(value):
        raise TavernGoldMaterializationError(f"{key} must be lowercase SHA-256 hex")
    return value


def _one(item: dict[str, Any]) -> dict[str, object]:
    phrase = _text(item, "phrase_key")
    decision = _text(item, "decision")
    a_hash = _sha(item, "annotator_A_raw_sha256")
    b_hash = _sha(item, "annotator_B_raw_sha256")
    if decision == "SELECT_A":
        tier, kind, sources, hashes, annotators = GoldTier.GOLD_EXPERT, AnnotationKind.HUMAN_EXPERT, ["A"], [a_hash], 1
    elif decision == "SELECT_B":
        tier, kind, sources, hashes, annotators = GoldTier.GOLD_EXPERT, AnnotationKind.HUMAN_EXPERT, ["B"], [b_hash], 1
    elif decision == "PRESERVE_VARIANTS":
        tier, kind, sources, hashes, annotators = GoldTier.GOLD_VARIANT, AnnotationKind.HUMAN_VARIANT, ["A", "B"], [a_hash, b_hash], 2
    elif decision == "CONFIRM_EQUIVALENT":
        tier, kind, sources, hashes, annotators = GoldTier.GOLD_CONSENSUS, AnnotationKind.HUMAN_CONSENSUS, ["A", "B"], [a_hash, b_hash], 2
    elif decision in {"AMBIGUOUS", "ABSTAIN"}:
        return {
            "record_id": f"tavern:{phrase}", "phrase_key": phrase, "human_decision": decision,
            "gold_tier": GoldTier.QUARANTINE.value, "annotation_kind": AnnotationKind.HUMAN_REVIEWED.value,
            "adjudication_outcome": AdjudicationOutcome.AMBIGUOUS.value if decision == "AMBIGUOUS" else AdjudicationOutcome.ABSTAIN.value,
            "selected_sources": [], "selected_raw_label_sha256": [], "normalization_version": NORMALIZATION_VERSION,
            "raw_label_materialization_status": "QUARANTINED_NO_SELECTED_LABEL", "normalization_status": "NOT_APPLICABLE",
            "training_eligible": False,
        }
    else:
        raise TavernGoldMaterializationError(f"unsupported human decision: {decision}")
    gold = GoldRecord(
        record_id=f"tavern:{phrase}", gold_tier=tier, annotation_kind=kind,
        adjudication_outcome=AdjudicationOutcome.RESOLVED, raw_source_label=None,
        annotator_count=annotators,
        notes="raw label bytes remain external and are bound by selected_raw_label_sha256",
    )
    gold.validate()
    return {
        "record_id": gold.record_id, "phrase_key": phrase, "human_decision": decision,
        "gold_tier": gold.gold_tier.value, "annotation_kind": gold.annotation_kind.value,
        "adjudication_outcome": gold.adjudication_outcome.value, "annotator_count": gold.annotator_count,
        "selected_sources": sources, "selected_raw_label_sha256": hashes,
        "normalization_version": NORMALIZATION_VERSION,
        "raw_label_materialization_status": "HASH_BOUND_EXTERNAL_LABEL_PENDING",
        "normalization_status": "PENDING_DETERMINISTIC_CORPUS_ADAPTER", "training_eligible": False,
    }


def build_tavern_gold_materialization(
    data: object, *, artifact_sha256: str,
    expected_artifact_sha256: str = PINNED_VALIDATED_SHA256,
    expected_count: int = PINNED_COUNT,
) -> dict[str, object]:
    if artifact_sha256 != expected_artifact_sha256:
        raise TavernGoldMaterializationError("validated decision artifact SHA-256 mismatch")
    if not isinstance(data, dict) or data.get("schema_version") != ADJUDICATION_INPUT_SCHEMA:
        raise TavernGoldMaterializationError("unsupported adjudication schema")
    if data.get("source_corpus") != "TAVERN" or data.get("source_revision") != PINNED_TAVERN_REVISION:
        raise TavernGoldMaterializationError("source identity mismatch")
    if data.get("reviewer_type") != "HUMAN":
        raise TavernGoldMaterializationError("human reviewer required")
    if data.get("comparison_evidence_sha256") != PINNED_TAVERN_AB_COMPARISON_SHA256:
        raise TavernGoldMaterializationError("comparison digest mismatch")
    decisions = data.get("decisions")
    if not isinstance(decisions, list) or not all(isinstance(x, dict) for x in decisions):
        raise TavernGoldMaterializationError("decisions must be an array of objects")
    if len(decisions) != expected_count:
        raise TavernGoldMaterializationError("validated decision count mismatch")
    seen: set[str] = set()
    records: list[dict[str, object]] = []
    tiers: Counter[str] = Counter()
    for item in decisions:
        phrase = _text(item, "phrase_key")
        if phrase in seen:
            raise TavernGoldMaterializationError(f"duplicate phrase_key: {phrase}")
        seen.add(phrase)
        record = _one(item)
        records.append(record)
        tiers[str(record["gold_tier"])] += 1
    records.sort(key=lambda x: str(x["phrase_key"]))
    pending = sum(r["raw_label_materialization_status"] == "HASH_BOUND_EXTERNAL_LABEL_PENDING" for r in records)
    return {
        "schema_version": MATERIALIZATION_SCHEMA, "source_corpus": "TAVERN",
        "source_revision": PINNED_TAVERN_REVISION, "validated_human_decisions_sha256": artifact_sha256,
        "record_count": len(records), "gold_tier_counts": {k: tiers[k] for k in sorted(tiers)},
        "hash_bound_external_label_pending_count": pending, "normalization_version": NORMALIZATION_VERSION,
        "records": records, "gold_assignment_authorized": True,
        "partition_assignment_authorized": False, "training_authorized": False,
    }


def build_tavern_gold_materialization_from_file(path: str | Path) -> dict[str, object]:
    p = Path(path)
    if p.is_symlink():
        raise TavernGoldMaterializationError("symlink input rejected")
    meta = p.stat()
    if not stat.S_ISREG(meta.st_mode) or meta.st_size > MAX_INPUT_BYTES:
        raise TavernGoldMaterializationError("input must be a bounded regular file")
    raw = p.read_bytes()
    if len(raw) > MAX_INPUT_BYTES:
        raise TavernGoldMaterializationError("input exceeds bounded size after read")
    return build_tavern_gold_materialization(
        load_bounded_json(p, max_bytes=MAX_INPUT_BYTES), artifact_sha256=hashlib.sha256(raw).hexdigest()
    )


def build_tavern_gold_materialization_summary(plan: object) -> dict[str, object]:
    if not isinstance(plan, dict) or plan.get("schema_version") != MATERIALIZATION_SCHEMA:
        raise TavernGoldMaterializationError("unsupported materialization plan")
    if plan.get("training_authorized") is not False:
        raise TavernGoldMaterializationError("materialization cannot authorize training")
    return {
        "schema_version": SUMMARY_SCHEMA, "source_corpus": plan["source_corpus"],
        "source_revision": plan["source_revision"], "validated_human_decisions_sha256": plan["validated_human_decisions_sha256"],
        "record_count": plan["record_count"], "gold_tier_counts": plan["gold_tier_counts"],
        "hash_bound_external_label_pending_count": plan["hash_bound_external_label_pending_count"],
        "normalization_version": plan["normalization_version"], "gold_assignment_authorized": plan["gold_assignment_authorized"],
        "partition_assignment_authorized": False, "training_authorized": False,
    }


def canonical_tavern_gold_materialization_json(data: dict[str, object]) -> str:
    if data.get("schema_version") not in {MATERIALIZATION_SCHEMA, SUMMARY_SCHEMA}:
        raise TavernGoldMaterializationError("unsupported materialization schema")
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
