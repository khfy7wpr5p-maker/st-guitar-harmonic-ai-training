from __future__ import annotations

from collections import Counter
import hashlib
import json
from typing import Any

from .tavern_reviewed_split import (
    EXPECTED_RECORD_DISTRIBUTION,
    EXPECTED_SEED,
    SPLIT_SCHEMA,
)
from .tavern_structure import PINNED_TAVERN_REVISION

INNER_SPLIT_SCHEMA = "st-guitar-harmony-train-inner-split-v1"
SUMMARY_SCHEMA = "st-guitar-harmony-train-inner-split-summary-v1"
INNER_SEED_PREFIX = "st-stage1e-inner-v1"
MAX_SEED_INDEX = 10_000
INNER_DEV_BUCKET_WIDTH = 2500
MIN_INNER_TRAIN_FAMILIES = 12
MIN_INNER_DEV_FAMILIES = 4
EXPECTED_ORIGINAL_TRAIN_RECORDS = 487
EXPECTED_ORIGINAL_TRAIN_FAMILIES = 18
EXPECTED_INNER_SEED_INDEX = 3
EXPECTED_INNER_SEED = f"{INNER_SEED_PREFIX}:{EXPECTED_INNER_SEED_INDEX}"
EXPECTED_INNER_FAMILY_DISTRIBUTION = {"INNER_DEV": 4, "INNER_TRAIN": 14}
EXPECTED_INNER_RECORD_DISTRIBUTION = {"INNER_DEV": 122, "INNER_TRAIN": 365}
PINNED_INNER_SPLIT_MANIFEST_SHA256 = (
    "210424f0d3d49af4dbb441686df6597efd3ba9a60efb22628ee7876fcf6a492b"
)


class TrainInnerSplitError(ValueError):
    pass


def deterministic_inner_partition(canonical_work_id: str, *, seed: str) -> str:
    if not isinstance(canonical_work_id, str) or not canonical_work_id.strip():
        raise TrainInnerSplitError("canonical_work_id must be non-empty")
    if not isinstance(seed, str) or not seed.strip():
        raise TrainInnerSplitError("inner split seed must be non-empty")
    digest = hashlib.sha256(
        f"{seed}\x1f{canonical_work_id}".encode("utf-8")
    ).digest()
    bucket = int.from_bytes(digest[:8], "big") % 10_000
    return "INNER_DEV" if bucket < INNER_DEV_BUCKET_WIDTH else "INNER_TRAIN"


def choose_train_inner_seed(
    canonical_work_ids: list[str],
) -> tuple[str, int, dict[str, int]]:
    if len(canonical_work_ids) != len(set(canonical_work_ids)):
        raise TrainInnerSplitError("inner split work IDs must be unique")
    if len(canonical_work_ids) != EXPECTED_ORIGINAL_TRAIN_FAMILIES:
        raise TrainInnerSplitError(
            "inner split requires exactly the frozen original TRAIN work families"
        )
    for index in range(MAX_SEED_INDEX):
        seed = f"{INNER_SEED_PREFIX}:{index}"
        counts = Counter(
            deterministic_inner_partition(work_id, seed=seed)
            for work_id in canonical_work_ids
        )
        if (
            counts["INNER_TRAIN"] >= MIN_INNER_TRAIN_FAMILIES
            and counts["INNER_DEV"] >= MIN_INNER_DEV_FAMILIES
        ):
            return seed, index, {
                "INNER_DEV": counts["INNER_DEV"],
                "INNER_TRAIN": counts["INNER_TRAIN"],
            }
    raise TrainInnerSplitError("no identity-only inner split seed satisfies coverage")


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_train_inner_split(
    reviewed_split: object,
    *,
    expected_manifest_sha256: str | None = PINNED_INNER_SPLIT_MANIFEST_SHA256,
) -> dict[str, object]:
    if not isinstance(reviewed_split, dict):
        raise TrainInnerSplitError("reviewed split must be an object")
    if reviewed_split.get("schema_version") != SPLIT_SCHEMA:
        raise TrainInnerSplitError("unsupported reviewed split schema")
    if reviewed_split.get("source_corpus") != "TAVERN_REVIEWED_694":
        raise TrainInnerSplitError("reviewed split source subset mismatch")
    if reviewed_split.get("source_revision") != PINNED_TAVERN_REVISION:
        raise TrainInnerSplitError("reviewed split source revision mismatch")
    if reviewed_split.get("seed") != EXPECTED_SEED:
        raise TrainInnerSplitError("outer split seed changed")
    if reviewed_split.get("record_distribution") != EXPECTED_RECORD_DISTRIBUTION:
        raise TrainInnerSplitError("outer split record distribution changed")
    if reviewed_split.get("label_aware_seed_selection") is not False:
        raise TrainInnerSplitError("outer split must remain label-blind")
    if reviewed_split.get("augmentation_scope") != "TRAIN_ONLY":
        raise TrainInnerSplitError("augmentation scope changed")
    if reviewed_split.get("training_authorized") is not False:
        raise TrainInnerSplitError("outer split cannot pre-authorize training")

    source_records = reviewed_split.get("records")
    if not isinstance(source_records, list) or not all(
        isinstance(item, dict) for item in source_records
    ):
        raise TrainInnerSplitError("reviewed split records malformed")

    train_records = [
        item for item in source_records if item.get("partition") == "TRAIN"
    ]
    if len(train_records) != EXPECTED_ORIGINAL_TRAIN_RECORDS:
        raise TrainInnerSplitError("original TRAIN record count changed")
    if any(
        item.get("partition") not in {"TRAIN", "VALIDATION", "CALIBRATION", "HOLDOUT"}
        for item in source_records
    ):
        raise TrainInnerSplitError("unexpected outer partition")

    canonical_work_ids = sorted(
        {
            str(item.get("canonical_work_id"))
            for item in train_records
            if isinstance(item.get("canonical_work_id"), str)
            and item.get("canonical_work_id")
        }
    )
    if len(canonical_work_ids) != EXPECTED_ORIGINAL_TRAIN_FAMILIES:
        raise TrainInnerSplitError("original TRAIN work-family count changed")

    seed, seed_index, family_distribution = choose_train_inner_seed(
        canonical_work_ids
    )
    if seed != EXPECTED_INNER_SEED or seed_index != EXPECTED_INNER_SEED_INDEX:
        raise TrainInnerSplitError("identity-only inner seed search result changed")
    if family_distribution != EXPECTED_INNER_FAMILY_DISTRIBUTION:
        raise TrainInnerSplitError("inner work-family distribution changed")

    seen_phrases: set[str] = set()
    family_inner_partition: dict[str, str] = {}
    records: list[dict[str, object]] = []
    record_distribution: Counter[str] = Counter()

    for item in train_records:
        phrase_key = item.get("phrase_key")
        source_work_id = item.get("source_work_id")
        canonical_work_id = item.get("canonical_work_id")
        split_group_id = item.get("split_group_id")
        if (
            not isinstance(phrase_key, str)
            or not phrase_key
            or phrase_key in seen_phrases
        ):
            raise TrainInnerSplitError("TRAIN phrase keys must be unique and non-empty")
        seen_phrases.add(phrase_key)
        if not all(
            isinstance(value, str) and value
            for value in (source_work_id, canonical_work_id, split_group_id)
        ):
            raise TrainInnerSplitError("TRAIN identity is incomplete")
        if canonical_work_id != split_group_id:
            raise TrainInnerSplitError("frozen TAVERN work/split identity changed")
        if not phrase_key.startswith(f"{source_work_id}:"):
            raise TrainInnerSplitError("TRAIN phrase/source-work identity mismatch")

        inner_partition = deterministic_inner_partition(
            canonical_work_id, seed=seed
        )
        previous = family_inner_partition.setdefault(
            canonical_work_id, inner_partition
        )
        if previous != inner_partition:
            raise TrainInnerSplitError("work family spans inner partitions")
        record_distribution[inner_partition] += 1
        records.append(
            {
                "phrase_key": phrase_key,
                "source_work_id": source_work_id,
                "canonical_work_id": canonical_work_id,
                "split_group_id": split_group_id,
                "original_partition": "TRAIN",
                "inner_partition": inner_partition,
            }
        )

    records.sort(key=lambda item: str(item["phrase_key"]))
    observed_record_distribution = {
        "INNER_DEV": record_distribution["INNER_DEV"],
        "INNER_TRAIN": record_distribution["INNER_TRAIN"],
    }
    if observed_record_distribution != EXPECTED_INNER_RECORD_DISTRIBUTION:
        raise TrainInnerSplitError("inner record distribution changed")
    if len(family_inner_partition) != EXPECTED_ORIGINAL_TRAIN_FAMILIES:
        raise TrainInnerSplitError("not all original TRAIN families were mapped")

    manifest_sha256 = _canonical_sha256(records)
    if (
        expected_manifest_sha256 is not None
        and manifest_sha256 != expected_manifest_sha256
    ):
        raise TrainInnerSplitError("inner split manifest digest changed")

    return {
        "schema_version": INNER_SPLIT_SCHEMA,
        "source_corpus": "TAVERN_REVIEWED_694",
        "source_revision": PINNED_TAVERN_REVISION,
        "outer_split_seed": EXPECTED_SEED,
        "outer_partition_scope": "TRAIN_ONLY",
        "inner_seed": seed,
        "inner_seed_index": seed_index,
        "inner_seed_selection_policy": (
            "LEXICOGRAPHIC_FIRST_IDENTITY_ONLY_MIN_FAMILY_COVERAGE"
        ),
        "label_aware_inner_seed_selection": False,
        "original_train_record_count": EXPECTED_ORIGINAL_TRAIN_RECORDS,
        "original_train_work_family_count": EXPECTED_ORIGINAL_TRAIN_FAMILIES,
        "inner_work_family_distribution": family_distribution,
        "inner_record_distribution": observed_record_distribution,
        "records": records,
        "inner_split_manifest_sha256": manifest_sha256,
        "original_partition_mutated": False,
        "validation_available_to_iterative_development": False,
        "calibration_available_to_iterative_development": False,
        "holdout_available_to_iterative_development": False,
        "event_target_materialization_authorized": False,
        "model_v2_training_authorized": False,
        "production_authority": False,
    }


def build_train_inner_split_summary(data: object) -> dict[str, object]:
    if not isinstance(data, dict) or data.get("schema_version") != INNER_SPLIT_SCHEMA:
        raise TrainInnerSplitError("unsupported inner split schema")
    if data.get("model_v2_training_authorized") is not False:
        raise TrainInnerSplitError("inner split cannot authorize model-v2 training")
    fields = (
        "source_corpus",
        "source_revision",
        "outer_split_seed",
        "outer_partition_scope",
        "inner_seed",
        "inner_seed_index",
        "inner_seed_selection_policy",
        "label_aware_inner_seed_selection",
        "original_train_record_count",
        "original_train_work_family_count",
        "inner_work_family_distribution",
        "inner_record_distribution",
        "inner_split_manifest_sha256",
        "original_partition_mutated",
        "validation_available_to_iterative_development",
        "calibration_available_to_iterative_development",
        "holdout_available_to_iterative_development",
        "event_target_materialization_authorized",
        "model_v2_training_authorized",
        "production_authority",
    )
    result: dict[str, object] = {"schema_version": SUMMARY_SCHEMA}
    result.update({field: data[field] for field in fields})
    return result


def canonical_train_inner_split_json(data: dict[str, object]) -> str:
    if data.get("schema_version") not in {INNER_SPLIT_SCHEMA, SUMMARY_SCHEMA}:
        raise TrainInnerSplitError("unsupported inner split schema")
    return json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ) + "\n"
