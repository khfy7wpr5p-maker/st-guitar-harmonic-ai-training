from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import stat
from typing import Any

from .safe_ingest import load_bounded_json
from .split import Partition, deterministic_partition
from .tavern_adjudication import ADJUDICATION_INPUT_SCHEMA
from .tavern_gold_materialization import PINNED_VALIDATED_SHA256, PINNED_COUNT
from .tavern_lineage import _work_mapping
from .tavern_lineage_closure import EXPECTED_INACTIVE_DOCUMENTED_WORKS
from .tavern_structure import DOCUMENTED_WORK_IDS, PINNED_TAVERN_REVISION

SPLIT_SCHEMA = "st-tavern-reviewed-split-v1"
MAX_INPUT_BYTES = 1024 * 1024
SEED_PREFIX = "st-tavern-split-v1"
MAX_SEED_INDEX = 10_000
MIN_GROUPS = {
    Partition.TRAIN: 14,
    Partition.VALIDATION: 2,
    Partition.CALIBRATION: 2,
    Partition.HOLDOUT: 2,
}
EXPECTED_SEED_INDEX = 12
EXPECTED_SEED = f"{SEED_PREFIX}:{EXPECTED_SEED_INDEX}"
EXPECTED_RECORD_DISTRIBUTION = {
    "CALIBRATION": 41,
    "HOLDOUT": 41,
    "TRAIN": 487,
    "VALIDATION": 125,
}


class TavernReviewedSplitError(ValueError):
    pass


def _active_source_work_ids() -> frozenset[str]:
    return DOCUMENTED_WORK_IDS - EXPECTED_INACTIVE_DOCUMENTED_WORKS


def _canonical_for_source_work(source_work_id: str) -> str:
    if source_work_id not in _active_source_work_ids():
        raise TavernReviewedSplitError(f"work is not in reviewed active family set: {source_work_id}")
    return str(_work_mapping(source_work_id)["canonical_work_id"])


def choose_tavern_split_seed(canonical_work_ids: list[str]) -> tuple[str, int, dict[str, int]]:
    if len(canonical_work_ids) != len(set(canonical_work_ids)):
        raise TavernReviewedSplitError("canonical work IDs must be unique")
    if len(canonical_work_ids) != 24:
        raise TavernReviewedSplitError("reviewed split requires exactly 24 active work families")
    for index in range(MAX_SEED_INDEX):
        seed = f"{SEED_PREFIX}:{index}"
        counts: Counter[Partition] = Counter(deterministic_partition(work_id, seed=seed) for work_id in canonical_work_ids)
        if all(counts[p] >= minimum for p, minimum in MIN_GROUPS.items()):
            return seed, index, {p.value: counts[p] for p in sorted(MIN_GROUPS, key=lambda x: x.value)}
    raise TavernReviewedSplitError("no deterministic split seed satisfies minimum family coverage")


def build_tavern_reviewed_split(
    data: object, *, artifact_sha256: str,
    expected_artifact_sha256: str = PINNED_VALIDATED_SHA256,
    expected_count: int = PINNED_COUNT,
) -> dict[str, object]:
    if artifact_sha256 != expected_artifact_sha256:
        raise TavernReviewedSplitError("validated decision artifact SHA-256 mismatch")
    if not isinstance(data, dict) or data.get("schema_version") != ADJUDICATION_INPUT_SCHEMA:
        raise TavernReviewedSplitError("unsupported adjudication schema")
    if data.get("source_corpus") != "TAVERN" or data.get("source_revision") != PINNED_TAVERN_REVISION:
        raise TavernReviewedSplitError("source identity mismatch")
    decisions = data.get("decisions")
    if not isinstance(decisions, list) or not all(isinstance(x, dict) for x in decisions):
        raise TavernReviewedSplitError("decisions must be an array of objects")
    if len(decisions) != expected_count:
        raise TavernReviewedSplitError("decision count mismatch")

    active_canonical = sorted(_canonical_for_source_work(work) for work in _active_source_work_ids())
    seed, seed_index, family_distribution = choose_tavern_split_seed(active_canonical)
    if seed_index != EXPECTED_SEED_INDEX or seed != EXPECTED_SEED:
        raise TavernReviewedSplitError("deterministic seed search result changed")

    seen: set[str] = set()
    records: list[dict[str, object]] = []
    record_counts: Counter[str] = Counter()
    family_partitions: dict[str, str] = {}
    for item in decisions:
        phrase = item.get("phrase_key")
        if not isinstance(phrase, str) or ":" not in phrase:
            raise TavernReviewedSplitError("invalid phrase_key")
        if phrase in seen:
            raise TavernReviewedSplitError(f"duplicate phrase_key: {phrase}")
        seen.add(phrase)
        source_work = phrase.split(":", 1)[0]
        canonical = _canonical_for_source_work(source_work)
        partition = deterministic_partition(canonical, seed=seed)
        previous = family_partitions.setdefault(canonical, partition.value)
        if previous != partition.value:
            raise TavernReviewedSplitError(f"work family spans partitions: {canonical}")
        record_counts[partition.value] += 1
        records.append({
            "phrase_key": phrase,
            "source_work_id": source_work,
            "canonical_work_id": canonical,
            "split_group_id": canonical,
            "partition": partition.value,
        })
    records.sort(key=lambda x: str(x["phrase_key"]))
    observed = {k: record_counts[k] for k in sorted(record_counts)}
    if expected_count == PINNED_COUNT and observed != EXPECTED_RECORD_DISTRIBUTION:
        raise TavernReviewedSplitError(f"real reviewed split distribution changed: {observed}")
    if len(family_partitions) != 24:
        raise TavernReviewedSplitError("not all 24 reviewed work families are represented")

    return {
        "schema_version": SPLIT_SCHEMA,
        "source_corpus": "TAVERN_REVIEWED_694",
        "source_revision": PINNED_TAVERN_REVISION,
        "validated_human_decisions_sha256": artifact_sha256,
        "seed": seed,
        "seed_index": seed_index,
        "seed_selection_policy": "LEXICOGRAPHIC_FIRST_IDENTITY_ONLY_MIN_FAMILY_COVERAGE",
        "label_aware_seed_selection": False,
        "work_family_distribution": family_distribution,
        "record_distribution": observed,
        "record_count": len(records),
        "records": records,
        "cross_corpus_alias_partition_inheritance_required": True,
        "augmentation_scope": "TRAIN_ONLY",
        "partition_assignment_authorized": True,
        "training_authorized": False,
    }


def build_tavern_reviewed_split_from_file(path: str | Path) -> dict[str, object]:
    p = Path(path)
    if p.is_symlink():
        raise TavernReviewedSplitError("symlink input rejected")
    meta = p.stat()
    if not stat.S_ISREG(meta.st_mode) or meta.st_size > MAX_INPUT_BYTES:
        raise TavernReviewedSplitError("input must be a bounded regular file")
    raw = p.read_bytes()
    if len(raw) > MAX_INPUT_BYTES:
        raise TavernReviewedSplitError("input exceeds bounded size after read")
    return build_tavern_reviewed_split(
        load_bounded_json(p, max_bytes=MAX_INPUT_BYTES), artifact_sha256=hashlib.sha256(raw).hexdigest()
    )


def canonical_tavern_reviewed_split_json(data: dict[str, object]) -> str:
    if data.get("schema_version") != SPLIT_SCHEMA:
        raise TavernReviewedSplitError("unsupported reviewed split schema")
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
