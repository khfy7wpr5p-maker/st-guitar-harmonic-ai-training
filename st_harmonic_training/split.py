from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256

from .contracts import ContractError
from .identity import WorkIdentity


class Partition(StrEnum):
    TRAIN = "TRAIN"
    VALIDATION = "VALIDATION"
    CALIBRATION = "CALIBRATION"
    HOLDOUT = "HOLDOUT"
    EXTERNAL_HOLDOUT = "EXTERNAL_HOLDOUT"
    QUARANTINE = "QUARANTINE"


DEFAULT_BUCKETS = (
    (Partition.TRAIN, 7000),
    (Partition.VALIDATION, 1000),
    (Partition.CALIBRATION, 1000),
    (Partition.HOLDOUT, 1000),
)


def deterministic_partition(split_group_id: str, *, seed: str = "st-split-v1") -> Partition:
    if not split_group_id.strip():
        raise ContractError("split_group_id must be non-empty")
    digest = sha256(f"{seed}\x1f{split_group_id}".encode("utf-8")).digest()
    bucket = int.from_bytes(digest[:8], "big") % 10_000
    cursor = 0
    for partition, width in DEFAULT_BUCKETS:
        cursor += width
        if bucket < cursor:
            return partition
    raise AssertionError("partition buckets must cover 10,000 slots")


@dataclass(frozen=True)
class SplitRecord:
    identity: WorkIdentity
    partition: Partition


def assign_partition(identity: WorkIdentity, *, seed: str = "st-split-v1") -> SplitRecord:
    return SplitRecord(identity, deterministic_partition(identity.split_group_id, seed=seed))


def augmentation_allowed(partition: Partition) -> bool:
    return partition is Partition.TRAIN


def assert_training_label_access(partition: Partition) -> None:
    if partition is not Partition.TRAIN:
        raise PermissionError(f"training pipeline cannot read labels from {partition}")


def leakage_violations(records: list[SplitRecord]) -> list[str]:
    violations: set[str] = set()
    by_record_id = {record.identity.record_id: record for record in records}
    grouped: dict[str, set[Partition]] = defaultdict(set)

    for record in records:
        identity = record.identity
        grouped[f"work:{identity.canonical_work_id}"].add(record.partition)
        grouped[f"duplicate:{identity.duplicate_cluster_id}"].add(record.partition)
        grouped[f"split:{identity.split_group_id}"].add(record.partition)

    for key, partitions in grouped.items():
        if len(partitions) > 1:
            values = ",".join(sorted(partition.value for partition in partitions))
            violations.add(f"{key} spans partitions: {values}")

    for record in records:
        parent_id = record.identity.derivation_parent_id
        if parent_id and parent_id in by_record_id:
            parent = by_record_id[parent_id]
            if parent.partition is not record.partition:
                violations.add(
                    f"derivation:{parent_id}->{record.identity.record_id} spans partitions: "
                    f"{parent.partition.value},{record.partition.value}"
                )

    return sorted(violations)
