from __future__ import annotations

import copy
import unittest

from st_harmonic_training.normalization import NORMALIZED_FIELDS
from st_harmonic_training.offline_experiment import (
    OfflineExperimentError,
    build_experiment_summary,
    build_private_experiment_shards,
    require_locked_runtime,
    run_offline_experiment,
)
from st_harmonic_training.stage1b_entry_completion import ENTRY_COMPLETION_SCHEMA
from st_harmonic_training.tavern_kern_features import (
    ADAPTER_VERSION as FEATURE_ADAPTER_VERSION,
    FEATURE_SCHEMA,
    PINNED_SCORE_INPUT_MANIFEST_SHA256,
)
from st_harmonic_training.tavern_normalization_adapter import (
    ADAPTER_VERSION as TARGET_ADAPTER_VERSION,
    NORMALIZED_TARGET_SCHEMA,
)
from st_harmonic_training.tavern_reviewed_split import EXPECTED_SEED, SPLIT_SCHEMA
from st_harmonic_training.tavern_structure import PINNED_TAVERN_REVISION
from st_harmonic_training.training_payload import (
    PINNED_FEATURE_MANIFEST_SHA256,
    PINNED_NORMALIZED_TARGET_MANIFEST_SHA256,
)


class OfflineExperimentTests(unittest.TestCase):
    def label(self, roman: str = '["I"]', phrase: str = '["T"]'):
        result = {field: None for field in NORMALIZED_FIELDS}
        result["key"] = "C:"
        result["roman_numeral"] = roman
        result["phrase"] = phrase
        return result

    def entry(self):
        return {
            "schema_version": ENTRY_COMPLETION_SCHEMA,
            "source_corpus": "TAVERN_REVIEWED_694",
            "source_revision": PINNED_TAVERN_REVISION,
            "entry_gate_status": "PASS",
            "training_scope": "OFFLINE_EXPERIMENT_ONLY",
            "training_authorized": True,
            "production_authority": False,
            "calibration_access_during_training": False,
            "holdout_access_during_training": False,
            "holdout_access_during_model_selection": False,
        }

    def source_objects(self):
        phrases = [
            ("Beethoven/B063:00:01", "TRAIN", "g-train", {"KERN_ATOM::4c": 2}),
            ("Beethoven/B064:00:01", "VALIDATION", "g-val", {"KERN_ATOM::4c": 1}),
            ("Beethoven/B065:00:01", "CALIBRATION", "g-cal", {"KERN_ATOM::4d": 1}),
            ("Beethoven/B066:00:01", "HOLDOUT", "g-hold", {"KERN_ATOM::4e": 1}),
        ]
        features = {
            "schema_version": FEATURE_SCHEMA,
            "adapter_version": FEATURE_ADAPTER_VERSION,
            "source_corpus": "TAVERN_REVIEWED_694",
            "source_revision": PINNED_TAVERN_REVISION,
            "score_input_manifest_sha256": PINNED_SCORE_INPUT_MANIFEST_SHA256,
            "feature_manifest_sha256": PINNED_FEATURE_MANIFEST_SHA256,
            "training_authorized": False,
            "records": [
                {
                    "phrase_key": phrase,
                    "score_sha256": "a" * 64,
                    "feature_sha256": "b" * 64,
                    "features": vector,
                }
                for phrase, _, _, vector in phrases
            ],
        }
        targets = {
            "schema_version": NORMALIZED_TARGET_SCHEMA,
            "adapter_version": TARGET_ADAPTER_VERSION,
            "source_corpus": "TAVERN_REVIEWED_694",
            "source_revision": PINNED_TAVERN_REVISION,
            "normalized_target_manifest_sha256": PINNED_NORMALIZED_TARGET_MANIFEST_SHA256,
            "training_authorized": False,
            "records": [
                {
                    "phrase_key": phrase,
                    "decision": "SELECT_B",
                    "targets": [
                        {
                            "source": "B",
                            "raw_sha256": "c" * 64,
                            "normalized_st_label": self.label(),
                            "normalized_label_sha256": "d" * 64,
                        }
                    ],
                }
                for phrase, _, _, _ in phrases
            ],
        }
        split = {
            "schema_version": SPLIT_SCHEMA,
            "source_corpus": "TAVERN_REVIEWED_694",
            "source_revision": PINNED_TAVERN_REVISION,
            "seed": EXPECTED_SEED,
            "label_aware_seed_selection": False,
            "augmentation_scope": "TRAIN_ONLY",
            "training_authorized": False,
            "records": [
                {
                    "phrase_key": phrase,
                    "source_work_id": phrase.split(":", 1)[0],
                    "canonical_work_id": group,
                    "split_group_id": group,
                    "partition": partition,
                }
                for phrase, partition, group, _ in phrases
            ],
        }
        return features, targets, split

    def shards(self):
        features, targets, split = self.source_objects()
        return build_private_experiment_shards(
            features,
            targets,
            split,
            self.entry(),
            expected_partition_counts={"TRAIN": 1, "VALIDATION": 1},
            expected_target_counts={"TRAIN": 1, "VALIDATION": 1},
        )

    def test_sharder_never_serializes_calibration_or_holdout(self) -> None:
        shards = self.shards()
        self.assertEqual(set(shards), {"TRAIN", "VALIDATION"})
        serialized = repr(shards)
        self.assertNotIn("B065:00:01", serialized)
        self.assertNotIn("B066:00:01", serialized)
        self.assertEqual(
            shards["TRAIN"]["sealed_partitions_not_serialized"],
            ["CALIBRATION", "HOLDOUT"],
        )

    def test_runner_is_deterministic_and_offline_only(self) -> None:
        shards = self.shards()
        result = run_offline_experiment(
            shards["TRAIN"], shards["VALIDATION"], self.entry(), enforce_runtime=False
        )
        self.assertTrue(result["deterministic_rerun_match"])
        self.assertTrue(result["all_thresholds_pass"])
        self.assertEqual(result["validation_gate_status"], "PASS")
        self.assertFalse(result["calibration_accessed"])
        self.assertFalse(result["holdout_accessed"])
        self.assertFalse(result["production_authority"])
        summary = build_experiment_summary(result)
        self.assertNotIn("model_checkpoint", summary)
        self.assertTrue(summary["model_checkpoint_external_only"])

    def test_train_validation_split_group_overlap_fails_closed(self) -> None:
        features, targets, split = self.source_objects()
        split["records"][1]["split_group_id"] = "g-train"
        with self.assertRaises(OfflineExperimentError):
            build_private_experiment_shards(
                features,
                targets,
                split,
                self.entry(),
                expected_partition_counts={"TRAIN": 1, "VALIDATION": 1},
                expected_target_counts={"TRAIN": 1, "VALIDATION": 1},
            )

    def test_shard_tamper_fails_closed(self) -> None:
        shards = self.shards()
        train = copy.deepcopy(shards["TRAIN"])
        train["records"][0]["features"]["KERN_ATOM::4c"] = 999
        with self.assertRaises(OfflineExperimentError):
            run_offline_experiment(train, shards["VALIDATION"], self.entry(), enforce_runtime=False)

    def test_entry_authority_escalation_fails_closed(self) -> None:
        entry = self.entry()
        entry["production_authority"] = True
        features, targets, split = self.source_objects()
        with self.assertRaises(OfflineExperimentError):
            build_private_experiment_shards(
                features,
                targets,
                split,
                entry,
                expected_partition_counts={"TRAIN": 1, "VALIDATION": 1},
                expected_target_counts={"TRAIN": 1, "VALIDATION": 1},
            )

    def test_ci_runtime_matches_locked_python(self) -> None:
        require_locked_runtime()


if __name__ == "__main__":
    unittest.main()
