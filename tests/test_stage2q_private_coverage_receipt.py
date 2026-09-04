from __future__ import annotations

import json
import unittest

from st_harmonic_training.stage2q_private_coverage_receipt import (
    EXPECTED_EVENT_COUNT,
    EXPECTED_SOURCE_PATH_COUNT,
    Stage2QPrivateCoverageReceiptError,
    expected_receipt,
    validate_receipt,
)


class Stage2QPrivateCoverageReceiptTests(unittest.TestCase):
    def test_expected_receipt_is_valid_and_hold_only(self):
        receipt = validate_receipt(expected_receipt())
        self.assertEqual(receipt["source_path_count"], EXPECTED_SOURCE_PATH_COUNT)
        self.assertEqual(receipt["materialized_event_count"], EXPECTED_EVENT_COUNT)
        self.assertEqual(receipt["exact_aligned_event_count"], 546)
        self.assertEqual(receipt["unaligned_event_count"], 1308)
        self.assertEqual(receipt["fully_exact_aligned_source_path_count"], 137)
        self.assertFalse(receipt["exact_stage2g_event_to_runtime_frame_alignment_complete"])
        self.assertFalse(receipt["partial_alignment_auto_admission_authorized"])
        self.assertFalse(receipt["model_feature_materialization_authorized"])
        self.assertFalse(receipt["model_training_started"])
        self.assertFalse(receipt["production_authority"])
        self.assertTrue(receipt["deterministic_resolver_remains_authoritative"])
        self.assertEqual(receipt["decision"], "HOLD_PARTIAL_EXACT_ALIGNMENT_COVERAGE")

    def test_event_totals_close(self):
        receipt = expected_receipt()
        self.assertEqual(
            receipt["exact_aligned_event_count"] + receipt["unaligned_event_count"],
            EXPECTED_EVENT_COUNT,
        )
        self.assertEqual(
            sum(receipt["fold_exact_aligned_event_distribution"].values()),
            receipt["exact_aligned_event_count"],
        )
        self.assertEqual(
            sum(receipt["source_exact_aligned_event_distribution"].values()),
            receipt["exact_aligned_event_count"],
        )

    def test_path_totals_close(self):
        receipt = expected_receipt()
        self.assertEqual(
            sum(receipt["path_failure_reason_counts"].values())
            + receipt["fully_exact_aligned_source_path_count"],
            EXPECTED_SOURCE_PATH_COUNT,
        )

    def test_private_identifiers_and_targets_are_not_serialized(self):
        rendered = json.dumps(expected_receipt(), sort_keys=True)
        for forbidden in (
            "phrase_key",
            "function_token",
            "carrier_event_id",
            "source_annotation_sha256",
        ):
            self.assertNotIn(f'"{forbidden}"', rendered)

    def test_receipt_cannot_claim_merged_runner_reexecution(self):
        altered = expected_receipt()
        altered["merged_stage2q_v2_runner_reexecution_completed"] = True
        with self.assertRaises(Stage2QPrivateCoverageReceiptError):
            validate_receipt(altered)

    def test_receipt_cannot_lower_hold_by_mutation(self):
        altered = expected_receipt()
        altered["partial_alignment_auto_admission_authorized"] = True
        with self.assertRaises(Stage2QPrivateCoverageReceiptError):
            validate_receipt(altered)


if __name__ == "__main__":
    unittest.main()
