from __future__ import annotations

from copy import deepcopy
import unittest

from st_harmonic_training.split import deterministic_partition
from st_harmonic_training.stage1e_internal_cv import (
    DEVELOPMENT_SEED,
    EXPECTED_GROUPS_PER_FOLD,
    EXPECTED_TRAIN_RECORD_COUNT,
    EXPECTED_TRAIN_WORK_FAMILY_COUNT,
    FOLD_COUNT,
    PINNED_GROUP_PLAN_SHA256,
    Stage1EInternalCVError,
    _active_canonical_work_ids,
    build_stage1e_group_plan,
    build_stage1e_group_plan_summary,
    build_stage1e_summary,
    canonical_stage1e_json,
    expected_stage0_train_groups,
    materialize_stage1e_internal_cv,
)
from st_harmonic_training.tavern_reviewed_split import (
    EXPECTED_RECORD_DISTRIBUTION,
    EXPECTED_SEED,
)
from st_harmonic_training.tavern_structure import PINNED_TAVERN_REVISION
from st_harmonic_training.training_payload import PAYLOAD_SCHEMA


class Stage1EInternalCVTests(unittest.TestCase):
    SOURCE_DIGEST = "f" * 64

    def _groups_by_partition(self) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {
            "TRAIN": [],
            "VALIDATION": [],
            "CALIBRATION": [],
            "HOLDOUT": [],
        }
        for group in _active_canonical_work_ids():
            result[deterministic_partition(group, seed=EXPECTED_SEED).value].append(group)
        return result

    def _payload(self) -> dict[str, object]:
        groups = self._groups_by_partition()
        records: list[dict[str, object]] = []
        serial = 0
        for partition, total in EXPECTED_RECORD_DISTRIBUTION.items():
            partition_groups = groups[partition]
            base, remainder = divmod(total, len(partition_groups))
            for group_index, group in enumerate(partition_groups):
                count = base + (1 if group_index < remainder else 0)
                for _ in range(count):
                    serial += 1
                    records.append(
                        {
                            "phrase_key": f"synthetic:{serial:04d}",
                            "canonical_work_id": group,
                            "split_group_id": group,
                            "partition": partition,
                        }
                    )
        self.assertEqual(len(records), 694)
        return {
            "schema_version": PAYLOAD_SCHEMA,
            "source_corpus": "TAVERN_REVIEWED_694",
            "source_revision": PINNED_TAVERN_REVISION,
            "training_payload_manifest_sha256": self.SOURCE_DIGEST,
            "partition_distribution": dict(EXPECTED_RECORD_DISTRIBUTION),
            "augmentation_scope": "TRAIN_ONLY",
            "cross_corpus_alias_partition_inheritance_required": True,
            "holdout_labels_available_to_training": False,
            "holdout_labels_available_to_model_selection": False,
            "calibration_labels_available_to_parameter_fitting": False,
            "records": records,
        }

    def test_group_plan_is_pinned_label_blind_and_balanced(self) -> None:
        plan = build_stage1e_group_plan()
        self.assertEqual(plan["development_seed"], DEVELOPMENT_SEED)
        self.assertEqual(plan["fold_count"], FOLD_COUNT)
        self.assertEqual(plan["work_family_count"], EXPECTED_TRAIN_WORK_FAMILY_COUNT)
        self.assertEqual(
            plan["work_family_distribution"],
            {str(index): EXPECTED_GROUPS_PER_FOLD for index in range(FOLD_COUNT)},
        )
        self.assertEqual(plan["group_plan_manifest_sha256"], PINNED_GROUP_PLAN_SHA256)
        self.assertFalse(plan["label_aware_assignment"])
        self.assertFalse(plan["original_validation_access"])
        self.assertFalse(plan["calibration_access"])
        self.assertFalse(plan["holdout_access"])
        self.assertFalse(plan["quarantine_access"])
        self.assertFalse(plan["training_authorized"])

    def test_group_plan_contains_exactly_stage0_train_families(self) -> None:
        plan = build_stage1e_group_plan()
        observed = {item["split_group_id"] for item in plan["groups"]}
        self.assertEqual(observed, set(expected_stage0_train_groups()))
        for group in observed:
            self.assertEqual(deterministic_partition(group, seed=EXPECTED_SEED).value, "TRAIN")

    def test_private_materialization_uses_train_only(self) -> None:
        result = materialize_stage1e_internal_cv(
            self._payload(), expected_source_payload_sha256=self.SOURCE_DIGEST
        )
        self.assertEqual(result["record_count"], EXPECTED_TRAIN_RECORD_COUNT)
        self.assertEqual(result["work_family_count"], EXPECTED_TRAIN_WORK_FAMILY_COUNT)
        self.assertEqual(len(result["records"]), EXPECTED_TRAIN_RECORD_COUNT)
        self.assertTrue(
            all(
                item["split_group_id"] in set(expected_stage0_train_groups())
                for item in result["records"]
            )
        )
        self.assertFalse(result["original_validation_access"])
        self.assertFalse(result["calibration_access"])
        self.assertFalse(result["holdout_access"])
        self.assertFalse(result["event_target_materialization_authorized"])
        self.assertFalse(result["training_authorized"])
        self.assertFalse(result["production_authority"])

    def test_materialization_is_identity_only(self) -> None:
        result = materialize_stage1e_internal_cv(
            self._payload(), expected_source_payload_sha256=self.SOURCE_DIGEST
        )
        allowed = {
            "phrase_key",
            "canonical_work_id",
            "split_group_id",
            "development_fold",
        }
        for record in result["records"]:
            self.assertEqual(set(record), allowed)

    def test_group_crossing_original_partitions_fails_closed(self) -> None:
        payload = self._payload()
        records = payload["records"]
        train_group = expected_stage0_train_groups()[0]
        validation_record = next(item for item in records if item["partition"] == "VALIDATION")
        validation_record["canonical_work_id"] = train_group
        validation_record["split_group_id"] = train_group
        with self.assertRaises(Stage1EInternalCVError):
            materialize_stage1e_internal_cv(
                payload, expected_source_payload_sha256=self.SOURCE_DIGEST
            )

    def test_duplicate_phrase_fails_closed(self) -> None:
        payload = self._payload()
        payload["records"][1]["phrase_key"] = payload["records"][0]["phrase_key"]
        with self.assertRaises(Stage1EInternalCVError):
            materialize_stage1e_internal_cv(
                payload, expected_source_payload_sha256=self.SOURCE_DIGEST
            )

    def test_source_authority_tamper_fails_closed(self) -> None:
        for field in (
            "holdout_labels_available_to_training",
            "holdout_labels_available_to_model_selection",
            "calibration_labels_available_to_parameter_fitting",
        ):
            payload = self._payload()
            payload[field] = True
            with self.assertRaises(Stage1EInternalCVError):
                materialize_stage1e_internal_cv(
                    payload, expected_source_payload_sha256=self.SOURCE_DIGEST
                )

    def test_reordered_source_is_deterministic(self) -> None:
        payload_a = self._payload()
        payload_b = deepcopy(payload_a)
        payload_b["records"] = list(reversed(payload_b["records"]))
        result_a = materialize_stage1e_internal_cv(
            payload_a, expected_source_payload_sha256=self.SOURCE_DIGEST
        )
        result_b = materialize_stage1e_internal_cv(
            payload_b, expected_source_payload_sha256=self.SOURCE_DIGEST
        )
        self.assertEqual(canonical_stage1e_json(result_a), canonical_stage1e_json(result_b))

    def test_summary_preserves_fail_closed_authority(self) -> None:
        result = materialize_stage1e_internal_cv(
            self._payload(), expected_source_payload_sha256=self.SOURCE_DIGEST
        )
        summary = build_stage1e_summary(result)
        self.assertNotIn("records", summary)
        self.assertFalse(summary["training_authorized"])
        self.assertFalse(summary["production_authority"])
        plan_summary = build_stage1e_group_plan_summary()
        self.assertEqual(plan_summary["record_materialization_status"], "PENDING_PRIVATE_PAYLOAD")
        self.assertFalse(plan_summary["original_validation_access"])


if __name__ == "__main__":
    unittest.main()
