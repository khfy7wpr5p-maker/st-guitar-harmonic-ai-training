from __future__ import annotations

import unittest

from st_harmonic_training.stage2q_exact_runtime_alignment_coverage import (
    FRAME_JOIN_POLICY,
    JOINED_TIMING_POLICY,
    Stage2QExactRuntimeAlignmentError,
    _materialize_joined_carrier_and_frames,
    audit_exact_source_path,
    build_stage2q_contract,
    validate_stage2q_contract,
)


SCORE = b"""**kern\t**kern
*staff1\t*staff1
=1\t=1
4c\t2e
4d\t.
=2\t=2
*-\t*-
"""

JOINED = b"""**kern\t**kern\t**harm
*staff1\t*staff1\t*
=1\t=1\t=1
4c\t2e\t4I
4d\t.\t4V
=2\t=2\t=2
*-\t*-\t*-
"""

MID_FRAME_SCORE = b"""**kern
*staff1
=1
2c
=2
*-
"""

MID_FRAME_JOINED = b"""**kern\t**harm
*staff1\t*
=1\t=1
2c\t4I
.\t4V
=2\t=2
*-\t*-
"""


def events(*carrier_indices: int):
    return [
        {
            "function_event_index": index,
            "carrier_harmonic_event_index": carrier,
        }
        for index, carrier in enumerate(carrier_indices)
    ]


class Stage2QExactRuntimeAlignmentCoverageTests(unittest.TestCase):
    def test_contract_is_frozen_audit_only(self):
        contract = validate_stage2q_contract(build_stage2q_contract())
        self.assertTrue(contract["audit_only"])
        self.assertEqual(contract["joined_timing_policy"], JOINED_TIMING_POLICY)
        self.assertEqual(contract["frame_join_policy"], FRAME_JOIN_POLICY)
        self.assertFalse(contract["nearest_frame_matching_authorized"])
        self.assertFalse(contract["order_only_matching_authorized"])
        self.assertFalse(contract["inferred_onset_authorized"])
        self.assertFalse(contract["inferred_duration_authorized"])
        self.assertFalse(contract["teacher_function_token_used_for_alignment"])
        self.assertFalse(contract["model_feature_materialization_authorized"])
        self.assertFalse(contract["model_training_started"])
        self.assertFalse(contract["production_authority"])
        self.assertTrue(contract["deterministic_resolver_remains_authoritative"])

    def test_joined_exact_clock_materializes_two_carriers_and_two_frames(self):
        result = _materialize_joined_carrier_and_frames(JOINED)
        self.assertEqual(len(result["carrier_positions"]), 2)
        self.assertEqual(len(result["frames"]), 2)
        self.assertEqual(result["carrier_positions"][0]["measure_number"], 1)
        self.assertEqual(result["carrier_positions"][0]["onset"], {"numerator": 0, "denominator": 1})
        self.assertEqual(result["carrier_positions"][1]["onset"], {"numerator": 1, "denominator": 1})

    def test_exact_source_path_aligns_only_by_exact_frame_start(self):
        result = audit_exact_source_path(events(0, 1), score_bytes=SCORE, joined_bytes=JOINED)
        self.assertTrue(result["score_materializer_supported"])
        self.assertTrue(result["joined_exact_timing_supported"])
        self.assertTrue(result["score_joined_frames_equivalent"])
        self.assertTrue(result["fully_exact_aligned"])
        self.assertEqual(result["exact_aligned_event_count"], 2)
        self.assertEqual(result["event_failure_reasons"], {})

    def test_mid_frame_function_change_is_not_forced_to_runtime_frame(self):
        result = audit_exact_source_path(
            events(0, 1), score_bytes=MID_FRAME_SCORE, joined_bytes=MID_FRAME_JOINED
        )
        self.assertTrue(result["score_joined_frames_equivalent"])
        self.assertFalse(result["fully_exact_aligned"])
        self.assertEqual(result["exact_aligned_event_count"], 1)
        self.assertEqual(
            result["event_failure_reasons"],
            {"CARRIER_NOT_RUNTIME_FRAME_START": 1},
        )

    def test_score_joined_frame_mismatch_fails_closed(self):
        mismatched = JOINED.replace(b"4d", b"4f")
        result = audit_exact_source_path(events(0, 1), score_bytes=SCORE, joined_bytes=mismatched)
        self.assertFalse(result["score_joined_frames_equivalent"])
        self.assertEqual(result["exact_aligned_event_count"], 0)
        self.assertEqual(result["path_failure_reason"], "SCORE_JOINED_FRAME_MISMATCH")

    def test_extra_joined_spine_type_is_not_silently_ignored(self):
        extra = b"""**kern\t**harm\t**function
*staff1\t*\t*
=1\t=1\t=1
4c\t4I\tT
=2\t=2\t=2
*-\t*-\t*-
"""
        with self.assertRaises(Stage2QExactRuntimeAlignmentError):
            _materialize_joined_carrier_and_frames(extra)

    def test_joined_spine_path_change_is_rejected(self):
        dynamic = b"""**kern\t**harm
*staff1\t*
*^\t*
"""
        with self.assertRaises(Stage2QExactRuntimeAlignmentError):
            _materialize_joined_carrier_and_frames(dynamic)

    def test_out_of_range_carrier_is_unaligned_not_order_matched(self):
        result = audit_exact_source_path(events(0, 9), score_bytes=SCORE, joined_bytes=JOINED)
        self.assertFalse(result["fully_exact_aligned"])
        self.assertEqual(result["exact_aligned_event_count"], 1)
        self.assertEqual(result["event_failure_reasons"], {"CARRIER_INDEX_OUT_OF_RANGE": 1})

    def test_duplicate_runtime_frame_join_is_not_auto_admitted(self):
        result = audit_exact_source_path(events(0, 0), score_bytes=SCORE, joined_bytes=JOINED)
        self.assertFalse(result["fully_exact_aligned"])
        self.assertEqual(result["exact_aligned_event_count"], 0)
        self.assertEqual(
            result["event_failure_reasons"],
            {"MULTIPLE_FUNCTION_EVENTS_SAME_RUNTIME_FRAME": 2},
        )


if __name__ == "__main__":
    unittest.main()
