from __future__ import annotations

import unittest

from st_harmonic_training.tavern_reviewed_split import (
    EXPECTED_SEED,
    EXPECTED_SEED_INDEX,
    TavernReviewedSplitError,
    _active_source_work_ids,
    _canonical_for_source_work,
    build_tavern_reviewed_split,
    choose_tavern_split_seed,
)
from st_harmonic_training.tavern_structure import PINNED_TAVERN_REVISION


class TavernReviewedSplitTests(unittest.TestCase):
    def payload(self) -> dict[str, object]:
        return {
            "schema_version": "st-tavern-human-adjudication-v1",
            "source_corpus": "TAVERN",
            "source_revision": PINNED_TAVERN_REVISION,
            "decisions": [
                {"phrase_key": f"{work}:00:01"}
                for work in sorted(_active_source_work_ids())
            ],
        }

    def test_seed_search_is_identity_only_and_deterministic(self) -> None:
        canonical = sorted(_canonical_for_source_work(x) for x in _active_source_work_ids())
        seed, index, distribution = choose_tavern_split_seed(canonical)
        self.assertEqual(seed, EXPECTED_SEED)
        self.assertEqual(index, EXPECTED_SEED_INDEX)
        self.assertGreaterEqual(distribution["TRAIN"], 14)
        self.assertGreaterEqual(distribution["VALIDATION"], 2)
        self.assertGreaterEqual(distribution["CALIBRATION"], 2)
        self.assertGreaterEqual(distribution["HOLDOUT"], 2)

    def test_every_work_family_stays_in_one_partition(self) -> None:
        data = self.payload()
        result = build_tavern_reviewed_split(
            data, artifact_sha256="a"*64,
            expected_artifact_sha256="a"*64, expected_count=24,
        )
        self.assertEqual(result["seed"], EXPECTED_SEED)
        self.assertFalse(result["label_aware_seed_selection"])
        self.assertEqual(result["augmentation_scope"], "TRAIN_ONLY")
        self.assertTrue(result["partition_assignment_authorized"])
        self.assertFalse(result["training_authorized"])
        by_group = {}
        for record in result["records"]:
            previous = by_group.setdefault(record["split_group_id"], record["partition"])
            self.assertEqual(previous, record["partition"])

    def test_unknown_or_inactive_work_fails_closed(self) -> None:
        data = self.payload(); data["decisions"][0]["phrase_key"] = "Beethoven/B071:00:01"
        with self.assertRaises(TavernReviewedSplitError):
            build_tavern_reviewed_split(data, artifact_sha256="a"*64, expected_artifact_sha256="a"*64, expected_count=24)

    def test_duplicate_phrase_fails_closed(self) -> None:
        data = self.payload(); data["decisions"].append(dict(data["decisions"][0]))
        with self.assertRaises(TavernReviewedSplitError):
            build_tavern_reviewed_split(data, artifact_sha256="a"*64, expected_artifact_sha256="a"*64, expected_count=25)

    def test_duplicate_canonical_ids_rejected_by_seed_search(self) -> None:
        canonical = sorted(_canonical_for_source_work(x) for x in _active_source_work_ids())
        with self.assertRaises(TavernReviewedSplitError):
            choose_tavern_split_seed(canonical[:-1] + [canonical[0]])


if __name__ == "__main__":
    unittest.main()
