from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import stat
from typing import Any

from .safe_ingest import load_bounded_json
from .tavern_adjudication import ADJUDICATION_INPUT_SCHEMA
from .tavern_gold_materialization import PINNED_VALIDATED_SHA256, PINNED_COUNT
from .tavern_lineage import _work_mapping
from .tavern_structure import DOCUMENTED_WORK_IDS, PINNED_TAVERN_REVISION

LINEAGE_CLOSURE_SCHEMA = "st-tavern-reviewed-lineage-closure-v1"
MAX_INPUT_BYTES = 1024 * 1024
EXPECTED_ACTIVE_WORKS = 24
EXPECTED_INACTIVE_DOCUMENTED_WORKS = frozenset({"Beethoven/B071", "Mozart/K025", "Mozart/K179"})


class TavernLineageClosureError(ValueError):
    pass


def _source_work_id(phrase_key: str) -> str:
    if not isinstance(phrase_key, str) or ":" not in phrase_key:
        raise TavernLineageClosureError("invalid phrase_key")
    work = phrase_key.split(":", 1)[0]
    if work not in DOCUMENTED_WORK_IDS:
        raise TavernLineageClosureError(f"unknown TAVERN work family: {work}")
    return work


def build_tavern_reviewed_lineage_closure(
    data: object, *, artifact_sha256: str,
    expected_artifact_sha256: str = PINNED_VALIDATED_SHA256,
    expected_count: int = PINNED_COUNT,
) -> dict[str, object]:
    if artifact_sha256 != expected_artifact_sha256:
        raise TavernLineageClosureError("validated-decision artifact SHA-256 mismatch")
    if not isinstance(data, dict) or data.get("schema_version") != ADJUDICATION_INPUT_SCHEMA:
        raise TavernLineageClosureError("unsupported adjudication schema")
    if data.get("source_corpus") != "TAVERN" or data.get("source_revision") != PINNED_TAVERN_REVISION:
        raise TavernLineageClosureError("source identity mismatch")
    decisions = data.get("decisions")
    if not isinstance(decisions, list) or not all(isinstance(x, dict) for x in decisions):
        raise TavernLineageClosureError("decisions must be an array of objects")
    if len(decisions) != expected_count:
        raise TavernLineageClosureError("decision count mismatch")

    seen: set[str] = set()
    work_counts: Counter[str] = Counter()
    for item in decisions:
        phrase = item.get("phrase_key")
        if not isinstance(phrase, str) or not phrase:
            raise TavernLineageClosureError("decision missing phrase_key")
        if phrase in seen:
            raise TavernLineageClosureError(f"duplicate phrase_key: {phrase}")
        seen.add(phrase)
        work_counts[_source_work_id(phrase)] += 1

    active = frozenset(work_counts)
    inactive = DOCUMENTED_WORK_IDS - active
    if len(active) != EXPECTED_ACTIVE_WORKS or inactive != EXPECTED_INACTIVE_DOCUMENTED_WORKS:
        raise TavernLineageClosureError(
            f"reviewed work-family coverage mismatch: active={len(active)}, inactive={sorted(inactive)}"
        )

    families: list[dict[str, object]] = []
    for source_work_id in sorted(active):
        mapping = _work_mapping(source_work_id)
        families.append({
            "source_work_id": source_work_id,
            "canonical_work_id": mapping["canonical_work_id"],
            "split_group_id": mapping["split_group_id"],
            "reviewed_record_count": work_counts[source_work_id],
            "lineage_strength": mapping["lineage_strength"],
            "aliases": mapping["aliases"],
            "alias_partition_inheritance_required": True,
        })

    canonical_ids = [str(x["canonical_work_id"]) for x in families]
    if len(canonical_ids) != len(set(canonical_ids)):
        raise TavernLineageClosureError("canonical work families must be unique")
    if sum(int(x["reviewed_record_count"]) for x in families) != expected_count:
        raise TavernLineageClosureError("reviewed record total mismatch")

    return {
        "schema_version": LINEAGE_CLOSURE_SCHEMA,
        "source_corpus": "TAVERN_REVIEWED_694",
        "source_revision": PINNED_TAVERN_REVISION,
        "validated_human_decisions_sha256": artifact_sha256,
        "reviewed_record_count": expected_count,
        "active_work_family_count": len(families),
        "inactive_documented_work_ids": sorted(inactive),
        "families": families,
        "cross_corpus_aliases_bound": True,
        "partition_assignment_authorized": False,
        "training_authorized": False,
    }


def build_tavern_reviewed_lineage_closure_from_file(path: str | Path) -> dict[str, object]:
    p = Path(path)
    if p.is_symlink():
        raise TavernLineageClosureError("symlink input rejected")
    meta = p.stat()
    if not stat.S_ISREG(meta.st_mode) or meta.st_size > MAX_INPUT_BYTES:
        raise TavernLineageClosureError("input must be a bounded regular file")
    raw = p.read_bytes()
    if len(raw) > MAX_INPUT_BYTES:
        raise TavernLineageClosureError("input exceeds bounded size after read")
    return build_tavern_reviewed_lineage_closure(
        load_bounded_json(p, max_bytes=MAX_INPUT_BYTES), artifact_sha256=hashlib.sha256(raw).hexdigest()
    )


def canonical_tavern_reviewed_lineage_closure_json(data: dict[str, object]) -> str:
    if data.get("schema_version") != LINEAGE_CLOSURE_SCHEMA:
        raise TavernLineageClosureError("unsupported lineage closure schema")
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
