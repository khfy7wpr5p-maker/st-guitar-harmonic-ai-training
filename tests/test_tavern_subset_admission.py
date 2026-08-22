from __future__ import annotations

import copy
import unittest

from st_harmonic_training.tavern_gold_materialization import PINNED_VALIDATED_SHA256, SUMMARY_SCHEMA
from st_harmonic_training.tavern_structure import PINNED_TAVERN_REVISION
from st_harmonic_training.tavern_subset_admission import (
    TavernSubsetAdmissionError,
    build_tavern_reviewed_subset_admission,
    canonical_tavern_subset_admission_json,
)


class TavernSubsetAdmissionTests(unittest.TestCase):
    def summary(self) -> dict[str, object]:
        return {
            "schema_version": SUMMARY_SCHEMA,
            "source_corpus": "TAVERN",
            "source_revision": PINNED_TAVERN_REVISION,
            "validated_human_decisions_sha256": PINNED_VALIDATED_SHA256,
            "record_count": 694,
            "gold_tier_counts": {"GOLD_EXPERT": 641, "GOLD_VARIANT": 53},
            "hash_bound_external_label_pending_count": 694,
            "normalization_version": "st-harmony-normalization-v1",
            "gold_assignment_authorized": True,
            "partition_assignment_authorized": False,
            "training_authorized": False,
        }

    def test_reviewed_subset_is_ready_only_for_dataset_engineering(self) -> None:
        result = build_tavern_reviewed_subset_admission(self.summary())
        self.assertEqual(result["admitted_record_count"], 694)
        self.assertEqual(result["excluded_record_count"], 243)
        self.assertEqual(result["source_manifest"]["acquisition_status"], "READY")
        self.assertEqual(result["admission_scope"], "DATASET_ENGINEERING_ONLY")
        self.assertFalse(result["raw_label_realization_complete"])
        self.assertFalse(result["normalization_complete"])
        self.assertFalse(result["training_authorized"])

    def test_count_tamper_fails_closed(self) -> None:
        data = self.summary(); data["record_count"] = 693
        with self.assertRaises(TavernSubsetAdmissionError):
            build_tavern_reviewed_subset_admission(data)

    def test_gold_distribution_tamper_fails_closed(self) -> None:
        data = self.summary(); data["gold_tier_counts"] = {"GOLD_EXPERT": 694}
        with self.assertRaises(TavernSubsetAdmissionError):
            build_tavern_reviewed_subset_admission(data)

    def test_training_authority_escalation_fails_closed(self) -> None:
        data = self.summary(); data["training_authorized"] = True
        with self.assertRaises(TavernSubsetAdmissionError):
            build_tavern_reviewed_subset_admission(data)

    def test_missing_gold_authority_fails_closed(self) -> None:
        data = self.summary(); data["gold_assignment_authorized"] = False
        with self.assertRaises(TavernSubsetAdmissionError):
            build_tavern_reviewed_subset_admission(data)

    def test_output_is_deterministic(self) -> None:
        left = build_tavern_reviewed_subset_admission(self.summary())
        right = build_tavern_reviewed_subset_admission(copy.deepcopy(self.summary()))
        self.assertEqual(canonical_tavern_subset_admission_json(left), canonical_tavern_subset_admission_json(right))


if __name__ == "__main__":
    unittest.main()
