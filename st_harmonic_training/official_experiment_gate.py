from __future__ import annotations

import hashlib
import json
from typing import Any

from .offline_experiment import (
    SHARD_SCHEMA,
    SEALED_PARTITIONS,
    SOURCE_CORPUS,
    OfflineExperimentError,
    run_offline_experiment,
)
from .tavern_structure import PINNED_TAVERN_REVISION
from .training_payload import (
    PINNED_FEATURE_MANIFEST_SHA256,
    PINNED_NORMALIZED_TARGET_MANIFEST_SHA256,
    PINNED_TRAINING_PAYLOAD_MANIFEST_SHA256,
)

PINNED_PRIVATE_SHARD_MANIFESTS = {
    "TRAIN": "d70c99ab3b2823946c893cf7b0e085a6300074244700f136fe346b3f320377e9",
    "VALIDATION": "2201327a49cf8095829c61a0b98ef07f5384c281d6c6f4ef0d14030a5d4d9dc5",
}
PINNED_PRIVATE_SHARD_COUNTS = {
    "TRAIN": (487, 500),
    "VALIDATION": (125, 154),
}


def _canonical_records(records: object) -> bytes:
    return json.dumps(
        records, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def validate_pinned_private_shard(data: object, partition: str) -> dict[str, Any]:
    if partition not in PINNED_PRIVATE_SHARD_MANIFESTS:
        raise OfflineExperimentError("unsupported official shard partition")
    if not isinstance(data, dict) or data.get("schema_version") != SHARD_SCHEMA:
        raise OfflineExperimentError("unsupported official shard schema")
    if data.get("source_corpus") != SOURCE_CORPUS:
        raise OfflineExperimentError("official shard source subset mismatch")
    if data.get("source_revision") != PINNED_TAVERN_REVISION:
        raise OfflineExperimentError("official shard source revision mismatch")
    if data.get("partition") != partition:
        raise OfflineExperimentError("official shard partition mismatch")
    if data.get("sealed_partitions_not_serialized") != list(SEALED_PARTITIONS):
        raise OfflineExperimentError("official shard sealed-partition contract changed")
    if data.get("feature_manifest_sha256") != PINNED_FEATURE_MANIFEST_SHA256:
        raise OfflineExperimentError("official shard feature manifest changed")
    if data.get("normalized_target_manifest_sha256") != PINNED_NORMALIZED_TARGET_MANIFEST_SHA256:
        raise OfflineExperimentError("official shard target manifest changed")
    if data.get("training_payload_manifest_sha256") != PINNED_TRAINING_PAYLOAD_MANIFEST_SHA256:
        raise OfflineExperimentError("official shard payload manifest changed")
    if data.get("production_authority") is not False:
        raise OfflineExperimentError("official shard cannot grant production authority")

    expected_records, expected_targets = PINNED_PRIVATE_SHARD_COUNTS[partition]
    if data.get("record_count") != expected_records:
        raise OfflineExperimentError("official shard record count changed")
    if data.get("target_count") != expected_targets:
        raise OfflineExperimentError("official shard target count changed")
    records = data.get("records")
    if not isinstance(records, list) or len(records) != expected_records:
        raise OfflineExperimentError("official shard record payload count changed")
    target_count = 0
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise OfflineExperimentError("official shard record malformed")
        phrase = record.get("phrase_key")
        if not isinstance(phrase, str) or not phrase or phrase in seen:
            raise OfflineExperimentError("official shard phrase identity malformed")
        seen.add(phrase)
        if record.get("partition") != partition:
            raise OfflineExperimentError("official shard contains cross-partition record")
        targets = record.get("targets")
        if not isinstance(targets, list) or len(targets) not in {1, 2}:
            raise OfflineExperimentError("official shard target set malformed")
        target_count += len(targets)
    if target_count != expected_targets:
        raise OfflineExperimentError("official shard target payload count changed")

    observed = hashlib.sha256(_canonical_records(records)).hexdigest()
    if data.get("shard_manifest_sha256") != observed:
        raise OfflineExperimentError("official shard self-digest mismatch")
    if observed != PINNED_PRIVATE_SHARD_MANIFESTS[partition]:
        raise OfflineExperimentError("official shard does not match pinned private anchor")
    return data


def run_official_offline_experiment(
    train_shard: object,
    validation_shard: object,
    entry_completion: object,
) -> dict[str, object]:
    train = validate_pinned_private_shard(train_shard, "TRAIN")
    validation = validate_pinned_private_shard(validation_shard, "VALIDATION")
    return run_offline_experiment(
        train,
        validation,
        entry_completion,
        enforce_runtime=True,
    )
