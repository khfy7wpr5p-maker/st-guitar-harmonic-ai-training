from __future__ import annotations

import copy
import hashlib
import json
import unittest
from unittest.mock import patch

from st_harmonic_training.offline_experiment import (
    SEALED_PARTITIONS,
    SHARD_SCHEMA,
    OfflineExperimentError,
)
from st_harmonic_training.official_experiment_gate import (
    PINNED_PRIVATE_SHARD_MANIFESTS,
    validate_pinned_private_shard,
)
from st_harmonic_training.tavern_structure import PINNED_TAVERN_REVISION
from st_harmonic_training.training_payload import (
    PINNED_FEATURE_MANIFEST_SHA256,
    PINNED_NORMALIZED_TARGET_MANIFEST_SHA256,
    PINNED_TRAINING_PAYLOAD_MANIFEST_SHA256,
)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


class OfficialExperimentGateTests(unittest.TestCase):
    def shard(self):
        records = [
            {
                "phrase_key": "Beethoven/B063:00:01",
                "partition": "TRAIN",
                "split_group_id": "g1",
                "feature_sha256": "a" * 64,
                "features": {"KERN_ATOM::4c": 1},
                "targets": [
                    {
                        "key": "C:",
                        "local_key": None,
                        "roman_numeral": '["I"]',
                        "bass": None,
                        "inversion": None,
                        "chord_family": None,
                        "extension": None,
                        "suspension": None,
                        "alteration": None,
                        "phrase": '["T"]',
                        "cadence": None,
                    }
                ],
            }
        ]
        digest = hashlib.sha256(canonical(records)).hexdigest()
        return {
            "schema_version": SHARD_SCHEMA,
            "source_corpus": "TAVERN_REVIEWED_694",
            "source_revision": PINNED_TAVERN_REVISION,
            "partition": "TRAIN",
            "record_count": 1,
            "target_count": 1,
            "feature_manifest_sha256": PINNED_FEATURE_MANIFEST_SHA256,
            "normalized_target_manifest_sha256": PINNED_NORMALIZED_TARGET_MANIFEST_SHA256,
            "training_payload_manifest_sha256": PINNED_TRAINING_PAYLOAD_MANIFEST_SHA256,
            "sealed_partitions_not_serialized": list(SEALED_PARTITIONS),
            "parameter_fitting_allowed": True,
            "model_selection_evaluation_allowed": False,
            "records": records,
            "shard_manifest_sha256": digest,
            "production_authority": False,
        }, digest

    def test_real_pins_are_frozen(self) -> None:
        self.assertEqual(
            PINNED_PRIVATE_SHARD_MANIFESTS,
            {
                "TRAIN": "d70c99ab3b2823946c893cf7b0e085a6300074244700f136fe346b3f320377e9",
                "VALIDATION": "2201327a49cf8095829c61a0b98ef07f5384c281d6c6f4ef0d14030a5d4d9dc5",
            },
        )

    def test_pinned_gate_rejects_body_change_even_with_recomputed_self_digest(self) -> None:
        shard, digest = self.shard()
        with patch.dict(
            "st_harmonic_training.official_experiment_gate.PINNED_PRIVATE_SHARD_MANIFESTS",
            {"TRAIN": digest},
            clear=True,
        ), patch.dict(
            "st_harmonic_training.official_experiment_gate.PINNED_PRIVATE_SHARD_COUNTS",
            {"TRAIN": (1, 1)},
            clear=True,
        ):
            validate_pinned_private_shard(shard, "TRAIN")
            changed = copy.deepcopy(shard)
            changed["records"][0]["features"]["KERN_ATOM::4c"] = 2
            changed["shard_manifest_sha256"] = hashlib.sha256(
                canonical(changed["records"])
            ).hexdigest()
            with self.assertRaises(OfflineExperimentError):
                validate_pinned_private_shard(changed, "TRAIN")


if __name__ == "__main__":
    unittest.main()
