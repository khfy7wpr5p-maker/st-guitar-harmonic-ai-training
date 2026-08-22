from __future__ import annotations

import copy
import unittest

from st_harmonic_training.tavern_gold_materialization import PINNED_VALIDATED_SHA256
from st_harmonic_training.tavern_kern_features import ADAPTER_VERSION as FEATURE_ADAPTER_VERSION, FEATURE_SCHEMA
from st_harmonic_training.tavern_normalization_adapter import (
    ADAPTER_VERSION as TARGET_ADAPTER_VERSION,
    NORMALIZED_TARGET_SCHEMA,
)
from st_harmonic_training.tavern_reviewed_split import EXPECTED_SEED, SPLIT_SCHEMA
from st_harmonic_training.tavern_structure import PINNED_TAVERN_REVISION
from st_harmonic_training.training_payload import (
    PAYLOAD_SCHEMA,
    TrainingPayloadError,
    build_training_payload_manifest,
    canonical_training_payload_json,
)


class TrainingPayloadTests(unittest.TestCase):
    FEATURE_DIGEST = "a" * 64
    TARGET_DIGEST = "b" * 64

    def payloads(self):
        phrases = ["Beethoven/B063:00:01", "Mozart/K265:00:01"]
        features = {
            "schema_version": FEATURE_SCHEMA,
            "adapter_version": FEATURE_ADAPTER_VERSION,
            "source_corpus": "TAVERN_REVIEWED_694",
            "source_revision": PINNED_TAVERN_REVISION,
            "feature_manifest_sha256": self.FEATURE_DIGEST,
            "deterministic_feature_schema_complete": True,
            "training_authorized": False,
            "records": [
                {
                    "phrase_key": phrases[0],
                    "score_sha256": "1" * 64,
                    "feature_sha256": "2" * 64,
                },
                {
                    "phrase_key": phrases[1],
                    "score_sha256": "3" * 64,
                    "feature_sha256": "4" * 64,
                },
            ],
        }
        targets = {
            "schema_version": NORMALIZED_TARGET_SCHEMA,
            "adapter_version": TARGET_ADAPTER_VERSION,
            "source_corpus": "TAVERN_REVIEWED_694",
            "source_revision": PINNED_TAVERN_REVISION,
            "normalized_target_manifest_sha256": self.TARGET_DIGEST,
            "validated_human_decisions_sha256": PINNED_VALIDATED_SHA256,
            "normalization_complete": True,
            "training_authorized": False,
            "records": [
                {
                    "phrase_key": phrases[0],
                    "decision": "SELECT_B",
                    "targets": [
                        {
                            "source": "B",
                            "raw_sha256": "5" * 64,
                            "normalized_label_sha256": "6" * 64,
                        }
                    ],
                },
                {
                    "phrase_key": phrases[1],
                    "decision": "PRESERVE_VARIANTS",
                    "targets": [
                        {
                            "source": "A",
                            "raw_sha256": "7" * 64,
                            "normalized_label_sha256": "8" * 64,
                        },
                        {
                            "source": "B",
                            "raw_sha256": "9" * 64,
                            "normalized_label_sha256": "0" * 64,
                        },
                    ],
                },
            ],
        }
        split = {
            "schema_version": SPLIT_SCHEMA,
            "source_corpus": "TAVERN_REVIEWED_694",
            "source_revision": PINNED_TAVERN_REVISION,
            "seed": EXPECTED_SEED,
            "record_distribution": {"TRAIN": 1, "VALIDATION": 1},
            "label_aware_seed_selection": False,
            "augmentation_scope": "TRAIN_ONLY",
            "cross_corpus_alias_partition_inheritance_required": True,
            "training_authorized": False,
            "records": [
                {
                    "phrase_key": phrases[0],
                    "source_work_id": "Beethoven/B063",
                    "canonical_work_id": "st-work:beethoven:woo63",
                    "split_group_id": "st-work:beethoven:woo63",
                    "partition": "TRAIN",
                },
                {
                    "phrase_key": phrases[1],
                    "source_work_id": "Mozart/K265",
                    "canonical_work_id": "st-work:mozart:k265",
                    "split_group_id": "st-work:mozart:k265",
                    "partition": "VALIDATION",
                },
            ],
        }
        return features, targets, split

    def build(self, features=None, targets=None, split=None):
        f, t, s = self.payloads()
        return build_training_payload_manifest(
            features or f,
            targets or t,
            split or s,
            expected_record_count=2,
            expected_target_count=3,
            expected_partition_distribution={"TRAIN": 1, "VALIDATION": 1},
            expected_gold_counts={"GOLD_EXPERT": 1, "GOLD_VARIANT": 1},
            expected_feature_manifest_sha256=self.FEATURE_DIGEST,
            expected_target_manifest_sha256=self.TARGET_DIGEST,
            expected_payload_manifest_sha256=None,
        )

    def test_variant_target_set_is_preserved_and_training_stays_disabled(self):
        result = self.build()
        self.assertEqual(result["schema_version"], PAYLOAD_SCHEMA)
        self.assertEqual(result["record_count"], 2)
        self.assertEqual(result["target_count"], 3)
        variant = next(record for record in result["records"] if record["gold_tier"] == "GOLD_VARIANT")
        self.assertEqual([item["source"] for item in variant["target_set"]], ["A", "B"])
        self.assertFalse(result["holdout_labels_available_to_training"])
        self.assertFalse(result["training_authorized"])

    def test_target_phrase_mismatch_fails_closed(self):
        features, targets, split = self.payloads()
        targets["records"][1]["phrase_key"] = "Mozart/K265:00:02"
        with self.assertRaises(TrainingPayloadError):
            self.build(features, targets, split)

    def test_variant_collapse_fails_closed(self):
        features, targets, split = self.payloads()
        targets["records"][1]["targets"] = targets["records"][1]["targets"][:1]
        with self.assertRaises(TrainingPayloadError):
            self.build(features, targets, split)

    def test_split_group_leakage_fails_closed(self):
        features, targets, split = self.payloads()
        split["records"][1]["split_group_id"] = split["records"][0]["split_group_id"]
        with self.assertRaises(TrainingPayloadError):
            self.build(features, targets, split)

    def test_upstream_training_authority_fails_closed(self):
        features, targets, split = self.payloads()
        features["training_authorized"] = True
        with self.assertRaises(TrainingPayloadError):
            self.build(features, targets, split)

    def test_output_is_deterministic(self):
        left = self.build()
        right = self.build()
        self.assertEqual(
            canonical_training_payload_json(left),
            canonical_training_payload_json(right),
        )


if __name__ == "__main__":
    unittest.main()
