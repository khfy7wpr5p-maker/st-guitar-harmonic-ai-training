from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .safe_ingest import load_bounded_json
from .tavern_structure import PINNED_TAVERN_REVISION, STRUCTURE_SCHEMA

LINEAGE_SCHEMA = "st-tavern-lineage-v1"
WHEN_IN_ROME_REVISION = "1c61fe41b8c2910296d7d2bcbf6476c7c1f2fe35"
AUGMENTEDNET_REVISION = "46d3475651346fd9053db29bc2bfb7943a869b74"

BEETHOVEN_WOO = (63, 64, 65, 66, 68, 69, 70, 71, 72, 73, 75, 76, 77, 78, 80)
BEETHOVEN_OPUS = (34, 76)
MOZART_K = (25, 179, 265, 353, 354, 398, 455, 501, 573, 613)


class TavernLineageError(ValueError):
    pass


def _expected_source_work_ids() -> tuple[str, ...]:
    values = [f"Beethoven/B{number:03d}" for number in BEETHOVEN_WOO]
    values.extend(f"Beethoven/Opus{number}" for number in BEETHOVEN_OPUS)
    values.extend(f"Mozart/K{number:03d}" for number in MOZART_K)
    return tuple(sorted(values))


EXPECTED_SOURCE_WORK_IDS = _expected_source_work_ids()


def _work_mapping(source_work_id: str) -> dict[str, object]:
    composer, work = source_work_id.split("/", 1)
    if composer == "Beethoven" and work.startswith("B"):
        number = int(work[1:])
        catalog = f"WoO_{number}"
        canonical = f"st-work:beethoven:woo{number}"
        aug_base = f"tavern-beethoven-woo-{number}"
        wir_composer = "Beethoven,_Ludwig_van"
    elif composer == "Beethoven" and work.startswith("Opus"):
        number = int(work.removeprefix("Opus"))
        catalog = f"Op{number}"
        canonical = f"st-work:beethoven:op{number}"
        aug_base = f"tavern-beethoven-op{number}"
        wir_composer = "Beethoven,_Ludwig_van"
    elif composer == "Mozart" and work.startswith("K"):
        number = int(work[1:])
        catalog = f"K{number:03d}"
        canonical = f"st-work:mozart:k{number:03d}"
        aug_base = f"tavern-mozart-k{number:03d}"
        wir_composer = "Mozart,_Wolfgang_Amadeus"
    else:
        raise TavernLineageError(f"unsupported TAVERN work id: {source_work_id}")

    wir_path = f"Corpus/Variations_and_Grounds/{wir_composer}/_/{catalog}"
    return {
        "source_work_id": source_work_id,
        "canonical_work_id": canonical,
        "split_group_id": canonical,
        "lineage_strength": "DIRECT_SOURCE_LINEAGE",
        "aliases": {
            "TAVERN": [source_work_id],
            "When-in-Rome": [wir_path],
            "AugmentedNet": [f"{aug_base}-a", f"{aug_base}-b"],
        },
    }


def _validate_structure_evidence(data: object) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        raise TavernLineageError("TAVERN structure evidence must be an object")
    if data.get("schema_version") != STRUCTURE_SCHEMA:
        raise TavernLineageError("unsupported TAVERN structure evidence schema")
    if data.get("immutable_revision") != PINNED_TAVERN_REVISION:
        raise TavernLineageError("TAVERN structure evidence revision mismatch")
    if data.get("training_authorized") is not False:
        raise TavernLineageError("lineage must be built before any training authorization")

    summaries = data.get("work_summaries")
    if not isinstance(summaries, list) or not all(isinstance(item, dict) for item in summaries):
        raise TavernLineageError("work_summaries must be an array of objects")

    source_ids: list[str] = []
    for item in summaries:
        source_id = item.get("source_work_id")
        if not isinstance(source_id, str) or not source_id:
            raise TavernLineageError("work summary missing source_work_id")
        if item.get("partition") != "QUARANTINE":
            raise TavernLineageError(
                f"pre-lineage work must remain QUARANTINE: {source_id}"
            )
        if item.get("canonical_work_id") is not None or item.get("split_group_id") is not None:
            raise TavernLineageError(
                f"Stage 0-I evidence unexpectedly preassigned identity: {source_id}"
            )
        source_ids.append(source_id)

    if len(source_ids) != len(set(source_ids)):
        raise TavernLineageError("duplicate source_work_id in Stage 0-I evidence")
    if tuple(sorted(source_ids)) != EXPECTED_SOURCE_WORK_IDS:
        missing = sorted(set(EXPECTED_SOURCE_WORK_IDS) - set(source_ids))
        unexpected = sorted(set(source_ids) - set(EXPECTED_SOURCE_WORK_IDS)
        raise TavernLineageError(
            f"TAVERN work coverage mismatch; missing={missing}, unexpected={unexpected}"
        )
    return summaries


def build_tavern_lineage_evidence(structure_evidence: object) -> dict[str, object]:
    _validate_structure_evidence(structure_evidence)
    mappings = [_work_mapping(source_id) for source_id in EXPECTED_SOURCE_WORK_IDS]

    canonical_ids = [item["canonical_work_id"] for item in mappings]
    split_ids = [item["split_group_id"] for item in mappings]
    if len(canonical_ids) != len(set(canonical_ids)):
        raise TavernLineageError("canonical work ids must be unique")
    if len(split_ids) != len(set(split_ids)):
        raise TavernLineageError("split group ids must be unique")

    return {
        "schema_version": LINEAGE_SCHEMA,
        "source_corpus": "TAVERN",
        "source_revision": PINNED_TAVERN_REVISION,
        "lineage_sources": {
            "When-in-Rome": {
                "revision": WHEN_IN_ROME_REVISION,
                "evidence": "README states 27 Beethoven/Mozart variation sets were converted from TAVERN",
            },
            "AugmentedNet": {
                "revision": AUGMENTEDNET_REVISION,
                "evidence": "AugmentedNet/data/tavern.py pairs When-in-Rome TAVERN analyses with TAVERN scores",
            },
        },
        "work_family_count": len(mappings),
        "work_families": mappings,
        "remaining_blockers": [
            "PHRASE_STRUCTURE_RECONCILIATION_REQUIRED",
            "TEACHER_GOLD_ADJUDICATION_REQUIRED",
        ],
        "partition_assignment_authorized": False,
        "training_authorized": False,
    }


def build_tavern_lineage_evidence_from_file(path: str | Path) -> dict[str, object]:
    return build_tavern_lineage_evidence(load_bounded_json(path))


def canonical_lineage_json(evidence: dict[str, object]) -> str:
    if evidence.get("schema_version") != LINEAGE_SCHEMA:
        raise TavernLineageError("unsupported TAVERN lineage evidence schema")
    return json.dumps(
        evidence,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ) + "\n"
