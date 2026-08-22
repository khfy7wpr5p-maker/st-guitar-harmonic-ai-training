from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from typing import Any

from .tavern_gold_materialization import PINNED_COUNT, PINNED_VALIDATED_SHA256
from .tavern_kern_features import (
    ADAPTER_VERSION as FEATURE_ADAPTER_VERSION,
    FEATURE_SCHEMA,
)
from .tavern_normalization_adapter import (
    ADAPTER_VERSION as TARGET_ADAPTER_VERSION,
    NORMALIZED_TARGET_SCHEMA,
)
from .tavern_reviewed_split import (
    EXPECTED_RECORD_DISTRIBUTION,
    EXPECTED_SEED,
    SPLIT_SCHEMA,
)
from .tavern_structure import PINNED_TAVERN_REVISION

PAYLOAD_SCHEMA = "st-guitar-harmony-training-payload-manifest-v1"
SUMMARY_SCHEMA = "st-guitar-harmony-training-payload-summary-v1"
EXPECTED_RECORD_COUNT = PINNED_COUNT
EXPECTED_TARGET_COUNT = 747
EXPECTED_GOLD_COUNTS = {"GOLD_EXPERT": 641, "GOLD_VARIANT": 53}
PINNED_FEATURE_MANIFEST_SHA256 = (
    "184ea471894ff6cf376255d62e1f348c0878dc4c53939289b95fae40cb261126"
)
PINNED_NORMALIZED_TARGET_MANIFEST_SHA256 = (
    "195ec1ce2193f8560043a94f3ea99c8db69b830fff6e60313c88565714450a4c"
)
PINNED_TRAINING_PAYLOAD_MANIFEST_SHA256 = (
    "79272bbe51d8e850a6b77ca26aa1c7eafb4b728f5b3d25d60a1e62332616e27a"
)
SHA256_LEN = 64


class TrainingPayloadError(ValueError):
    pass


def _require_records(data: object, schema: str, label: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not isinstance(data, dict) or data.get("schema_version") != schema:
        raise TrainingPayloadError(f"unsupported {label} schema")
    records = data.get("records")
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        raise TrainingPayloadError(f"{label} records malformed")
    return data, records


def _index_unique(records: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in records:
        phrase = item.get("phrase_key")
        if not isinstance(phrase, str) or not phrase:
            raise TrainingPayloadError(f"{label} record missing phrase_key")
        if phrase in result:
            raise TrainingPayloadError(f"duplicate {label} phrase_key: {phrase}")
        result[phrase] = item
    return result


def _sha(value: object, label: str) -> str:
    if not isinstance(value, str) or len(value) != SHA256_LEN or any(
        c not in "0123456789abcdef" for c in value
    ):
        raise TrainingPayloadError(f"malformed {label} SHA-256")
    return value


def build_training_payload_manifest(
    features: object,
    normalized_targets: object,
    reviewed_split: object,
    *,
    expected_record_count: int = EXPECTED_RECORD_COUNT,
    expected_target_count: int = EXPECTED_TARGET_COUNT,
    expected_partition_distribution: dict[str, int] | None = None,
    expected_gold_counts: dict[str, int] | None = None,
    expected_feature_manifest_sha256: str = PINNED_FEATURE_MANIFEST_SHA256,
    expected_target_manifest_sha256: str = PINNED_NORMALIZED_TARGET_MANIFEST_SHA256,
    expected_payload_manifest_sha256: str | None = PINNED_TRAINING_PAYLOAD_MANIFEST_SHA256,
) -> dict[str, object]:
    if expected_partition_distribution is None:
        expected_partition_distribution = EXPECTED_RECORD_DISTRIBUTION
    if expected_gold_counts is None:
        expected_gold_counts = EXPECTED_GOLD_COUNTS

    feature_data, feature_records = _require_records(features, FEATURE_SCHEMA, "feature")
    target_data, target_records = _require_records(
        normalized_targets, NORMALIZED_TARGET_SCHEMA, "normalized target"
    )
    split_data, split_records = _require_records(
        reviewed_split, SPLIT_SCHEMA, "reviewed split"
    )

    for data, label in (
        (feature_data, "feature"),
        (target_data, "normalized target"),
        (split_data, "reviewed split"),
    ):
        if data.get("source_corpus") != "TAVERN_REVIEWED_694":
            raise TrainingPayloadError(f"{label} source subset mismatch")
        if data.get("source_revision") != PINNED_TAVERN_REVISION:
            raise TrainingPayloadError(f"{label} source revision mismatch")
        if data.get("training_authorized") is not False:
            raise TrainingPayloadError(f"{label} unexpectedly authorizes training")

    if feature_data.get("adapter_version") != FEATURE_ADAPTER_VERSION:
        raise TrainingPayloadError("feature adapter version mismatch")
    if feature_data.get("feature_manifest_sha256") != expected_feature_manifest_sha256:
        raise TrainingPayloadError("feature manifest digest mismatch")
    if feature_data.get("deterministic_feature_schema_complete") is not True:
        raise TrainingPayloadError("feature schema is not complete")

    if target_data.get("adapter_version") != TARGET_ADAPTER_VERSION:
        raise TrainingPayloadError("target adapter version mismatch")
    if target_data.get("normalized_target_manifest_sha256") != expected_target_manifest_sha256:
        raise TrainingPayloadError("normalized-target manifest digest mismatch")
    if target_data.get("normalization_complete") is not True:
        raise TrainingPayloadError("target normalization is not complete")
    if target_data.get("validated_human_decisions_sha256") != PINNED_VALIDATED_SHA256:
        raise TrainingPayloadError("validated human-decision digest mismatch")

    if split_data.get("seed") != EXPECTED_SEED:
        raise TrainingPayloadError("split seed mismatch")
    if split_data.get("record_distribution") != expected_partition_distribution:
        raise TrainingPayloadError("split record distribution mismatch")
    if split_data.get("label_aware_seed_selection") is not False:
        raise TrainingPayloadError("split seed must remain label-blind")
    if split_data.get("augmentation_scope") != "TRAIN_ONLY":
        raise TrainingPayloadError("augmentation scope must remain TRAIN_ONLY")
    if split_data.get("cross_corpus_alias_partition_inheritance_required") is not True:
        raise TrainingPayloadError("cross-corpus partition inheritance is not enforced")

    if not (
        len(feature_records)
        == len(target_records)
        == len(split_records)
        == expected_record_count
    ):
        raise TrainingPayloadError("payload component record counts differ")

    feature_by_phrase = _index_unique(feature_records, "feature")
    target_by_phrase = _index_unique(target_records, "target")
    split_by_phrase = _index_unique(split_records, "split")
    phrase_set = set(feature_by_phrase)
    if phrase_set != set(target_by_phrase) or phrase_set != set(split_by_phrase):
        raise TrainingPayloadError("payload component phrase sets differ")

    partition_counts: Counter[str] = Counter()
    gold_counts: Counter[str] = Counter()
    target_count = 0
    split_group_partitions: dict[str, set[str]] = defaultdict(set)
    records: list[dict[str, object]] = []

    for phrase in sorted(phrase_set):
        feature = feature_by_phrase[phrase]
        target = target_by_phrase[phrase]
        split = split_by_phrase[phrase]

        partition = split.get("partition")
        if partition not in {"TRAIN", "VALIDATION", "CALIBRATION", "HOLDOUT"}:
            raise TrainingPayloadError(f"unsupported partition for {phrase}")
        source_work_id = split.get("source_work_id")
        canonical_work_id = split.get("canonical_work_id")
        split_group_id = split.get("split_group_id")
        if not all(
            isinstance(value, str) and value
            for value in (source_work_id, canonical_work_id, split_group_id)
        ):
            raise TrainingPayloadError(f"split identity missing for {phrase}")
        if not phrase.startswith(f"{source_work_id}:"):
            raise TrainingPayloadError(f"phrase/source-work mismatch for {phrase}")
        split_group_partitions[str(split_group_id)].add(str(partition))

        decision = target.get("decision")
        targets = target.get("targets")
        if decision not in {"SELECT_A", "SELECT_B", "PRESERVE_VARIANTS"}:
            raise TrainingPayloadError(f"unsupported human decision for {phrase}")
        if not isinstance(targets, list) or not all(
            isinstance(item, dict) for item in targets
        ):
            raise TrainingPayloadError(f"target set malformed for {phrase}")
        expected_target_set_size = 2 if decision == "PRESERVE_VARIANTS" else 1
        if len(targets) != expected_target_set_size:
            raise TrainingPayloadError(f"decision/target-set size mismatch for {phrase}")

        target_set: list[dict[str, str]] = []
        seen_sources: set[str] = set()
        for item in targets:
            source = item.get("source")
            if source not in {"A", "B"} or source in seen_sources:
                raise TrainingPayloadError(f"invalid/duplicate target source for {phrase}")
            seen_sources.add(str(source))
            target_set.append(
                {
                    "source": str(source),
                    "raw_sha256": _sha(item.get("raw_sha256"), "raw target"),
                    "normalized_label_sha256": _sha(
                        item.get("normalized_label_sha256"), "normalized target"
                    ),
                }
            )
        target_set.sort(key=lambda item: item["source"])

        if decision == "SELECT_A" and [item["source"] for item in target_set] != ["A"]:
            raise TrainingPayloadError(f"SELECT_A source mismatch for {phrase}")
        if decision == "SELECT_B" and [item["source"] for item in target_set] != ["B"]:
            raise TrainingPayloadError(f"SELECT_B source mismatch for {phrase}")
        if decision == "PRESERVE_VARIANTS" and [
            item["source"] for item in target_set
        ] != ["A", "B"]:
            raise TrainingPayloadError(f"variant source set mismatch for {phrase}")

        gold_tier = (
            "GOLD_VARIANT" if decision == "PRESERVE_VARIANTS" else "GOLD_EXPERT"
        )
        record = {
            "phrase_key": phrase,
            "source_work_id": source_work_id,
            "canonical_work_id": canonical_work_id,
            "split_group_id": split_group_id,
            "partition": partition,
            "gold_tier": gold_tier,
            "human_decision": decision,
            "score_sha256": _sha(feature.get("score_sha256"), "score input"),
            "feature_sha256": _sha(feature.get("feature_sha256"), "feature"),
            "target_set": target_set,
        }
        records.append(record)
        partition_counts[str(partition)] += 1
        gold_counts[gold_tier] += 1
        target_count += len(target_set)

    leakage = {
        group: sorted(partitions)
        for group, partitions in split_group_partitions.items()
        if len(partitions) != 1
    }
    if leakage:
        raise TrainingPayloadError(f"split groups span partitions: {leakage}")

    observed_partition_counts = {
        key: partition_counts[key] for key in sorted(partition_counts)
    }
    if observed_partition_counts != expected_partition_distribution:
        raise TrainingPayloadError("payload partition distribution changed")
    observed_gold_counts = {key: gold_counts[key] for key in sorted(gold_counts)}
    if observed_gold_counts != expected_gold_counts:
        raise TrainingPayloadError("payload gold distribution changed")
    if target_count != expected_target_count:
        raise TrainingPayloadError("payload target count changed")

    manifest_bytes = json.dumps(
        records, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    if (
        expected_payload_manifest_sha256 is not None
        and manifest_sha256 != expected_payload_manifest_sha256
    ):
        raise TrainingPayloadError("training payload manifest digest changed")

    return {
        "schema_version": PAYLOAD_SCHEMA,
        "source_corpus": "TAVERN_REVIEWED_694",
        "source_revision": PINNED_TAVERN_REVISION,
        "feature_adapter_version": FEATURE_ADAPTER_VERSION,
        "feature_manifest_sha256": expected_feature_manifest_sha256,
        "target_adapter_version": TARGET_ADAPTER_VERSION,
        "normalized_target_manifest_sha256": expected_target_manifest_sha256,
        "validated_human_decisions_sha256": PINNED_VALIDATED_SHA256,
        "split_seed": EXPECTED_SEED,
        "record_count": len(records),
        "target_count": target_count,
        "partition_distribution": observed_partition_counts,
        "gold_tier_counts": observed_gold_counts,
        "variant_record_count": observed_gold_counts.get("GOLD_VARIANT", 0),
        "augmentation_scope": "TRAIN_ONLY",
        "holdout_labels_available_to_training": False,
        "holdout_labels_available_to_model_selection": False,
        "calibration_labels_available_to_parameter_fitting": False,
        "cross_corpus_alias_partition_inheritance_required": True,
        "training_payload_manifest_sha256": manifest_sha256,
        "records": records,
        "score_input_realization_complete": True,
        "deterministic_feature_schema_complete": True,
        "training_payload_manifest_complete": True,
        "model_implementation_complete": False,
        "model_training_started": False,
        "training_authorized": False,
        "production_authority": False,
    }


def build_training_payload_summary(data: object) -> dict[str, object]:
    if not isinstance(data, dict) or data.get("schema_version") != PAYLOAD_SCHEMA:
        raise TrainingPayloadError("unsupported training payload schema")
    if data.get("training_payload_manifest_complete") is not True:
        raise TrainingPayloadError("training payload manifest incomplete")
    if data.get("training_authorized") is not False:
        raise TrainingPayloadError("payload stage cannot authorize training")
    fields = (
        "source_corpus",
        "source_revision",
        "feature_adapter_version",
        "feature_manifest_sha256",
        "target_adapter_version",
        "normalized_target_manifest_sha256",
        "validated_human_decisions_sha256",
        "split_seed",
        "record_count",
        "target_count",
        "partition_distribution",
        "gold_tier_counts",
        "variant_record_count",
        "augmentation_scope",
        "holdout_labels_available_to_training",
        "holdout_labels_available_to_model_selection",
        "calibration_labels_available_to_parameter_fitting",
        "cross_corpus_alias_partition_inheritance_required",
        "training_payload_manifest_sha256",
    )
    result: dict[str, object] = {"schema_version": SUMMARY_SCHEMA}
    result.update({field: data[field] for field in fields})
    result.update(
        {
            "training_payload_manifest_complete": True,
            "model_implementation_complete": False,
            "model_training_started": False,
            "training_authorized": False,
            "production_authority": False,
        }
    )
    return result


def canonical_training_payload_json(data: dict[str, object]) -> str:
    if data.get("schema_version") not in {PAYLOAD_SCHEMA, SUMMARY_SCHEMA}:
        raise TrainingPayloadError("unsupported training payload schema")
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
