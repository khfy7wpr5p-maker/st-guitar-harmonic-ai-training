from __future__ import annotations

import unittest

from st_harmonic_training.stage2q_corpus_reality_alignment import (
    FRAME_JOIN_POLICY,
    JOINED_TIMING_POLICY,
    STAFF_MAPPING_POLICY,
    Stage2QCorpusRealityError,
    _materialize_joined_with_score_staffs,
    _score_staff_map,
    audit_exact_source_path_v2,
    build_stage2q_v2_contract,
    validate_stage2q_v2_contract,
)


SCORE = b"""**kern\t**kern
*staff2\t*staff1
=1\t=1
4C\t2e
4D\t.
=2\t=2
*-\t*-
"""

JOINED = b"""**function\t**harm\t**kern\t**kern
*\t*\t*\t*
=1\t=1\t=1\t=1
T\t4I\t4C\t2e
D\t4V\t4D\t.
=2\t=2\t=2\t=2
*-\t*-\t*-\t*-
"""

FUNCTION_ONLY_ROW = b"""**function\t**harm\t**kern\t**kern
*\t*\t*\t*
=1\t=1\t=1\t=1
T\t2I\t2C\t2e
D\t.\t.\t.
=2\t=2\t=2\t=2
*-\t*-\t*-\t*-
"""


def events(*carrier_indices: int):
    return [
        {
            "function_event_index": index,
            "carrier_harmonic_event_index": carrier,
        }
        for index, carrier in enumerate(carrier_indices)
    ]


class Stage2QCorpusRealityAlignmentTests(unittest.TestCase):
    def test_contract_freezes_corpus_reality_without_reopening_training(self):
        contract = validate_stage2q_v2_contract(build_stage2q_v2_contract())
        self.assertTrue(contract["audit_only"])
        self.assertEqual(contract["joined_timing_policy"], JOINED_TIMING_POLICY)
        self.assertEqual(contract["staff_mapping_policy"], STAFF_MAPPING_POLICY)
        self.assertEqual(contract["frame_join_policy"], FRAME_JOIN_POLICY)
        self.assertFalse(contract["joined_function_spine_value_used"])
        self.assertTrue(contract["joined_function_spine_presence_guard_only"])
        self.assertFalse(contract["function_data_without_same_row_harmonic_data_authorized"])
        self.assertFalse(contract["nearest_frame_matching_authorized"])
        self.assertFalse(contract["order_only_matching_authorized"])
        self.assertFalse(contract["inferred_onset_authorized"])
        self.assertFalse(contract["inferred_duration_authorized"])
        self.assertFalse(contract["model_feature_materialization_authorized"])
        self.assertFalse(contract["model_training_started"])
        self.assertFalse(contract["production_authority"])
        self.assertTrue(contract["deterministic_resolver_remains_authoritative"])

    def test_score_staff_mapping_is_exact_and_ordinal(self):
        self.assertEqual(_score_staff_map(SCORE), (2, 1))

    def test_real_joined_shape_can_use_score_staff_mapping_without_function_values(self):
        joined = _materialize_joined_with_score_staffs(JOINED, score_staffs=(2, 1))
        self.assertEqual(len(joined["carrier_positions"]), 2)
        self.assertEqual(len(joined["frames"]), 2)
        first_events = joined["frames"][0]["events"]
        self.assertEqual({event["staff"] for event in first_events}, {1, 2})
        self.assertEqual(joined["carrier_positions"][0]["onset"], {"numerator": 0, "denominator": 1})
        self.assertEqual(joined["carrier_positions"][1]["onset"], {"numerator": 1, "denominator": 1})

    def test_exact_path_aligns_under_real_joined_shape(self):
        result = audit_exact_source_path_v2(events(0, 1), score_bytes=SCORE, joined_bytes=JOINED)
        self.assertTrue(result["score_materializer_supported"])
        self.assertTrue(result["joined_exact_timing_supported"])
        self.assertTrue(result["score_joined_frames_equivalent"])
        self.assertTrue(result["fully_exact_aligned"])
        self.assertEqual(result["exact_aligned_event_count"], 2)
        self.assertEqual(result["event_failure_reasons"], {})

    def test_function_data_without_harmonic_carrier_fails_closed(self):
        with self.assertRaises(Stage2QCorpusRealityError):
            _materialize_joined_with_score_staffs(
                FUNCTION_ONLY_ROW,
                score_staffs=(2, 1),
            )

    def test_joined_kern_spine_count_must_equal_score(self):
        with self.assertRaises(Stage2QCorpusRealityError):
            _materialize_joined_with_score_staffs(JOINED, score_staffs=(1,))

    def test_joined_unknown_spine_type_is_rejected(self):
        bad = JOINED.replace(b"**function", b"**foo", 1)
        with self.assertRaises(Stage2QCorpusRealityError):
            _materialize_joined_with_score_staffs(bad, score_staffs=(2, 1))

    def test_joined_explicit_staff_conflict_is_rejected(self):
        bad = JOINED.replace(b"*\t*\t*\t*", b"*\t*\t*staff1\t*staff1", 1)
        with self.assertRaises(Stage2QCorpusRealityError):
            _materialize_joined_with_score_staffs(bad, score_staffs=(2, 1))

    def test_out_of_range_carrier_is_not_order_matched(self):
        result = audit_exact_source_path_v2(events(0, 9), score_bytes=SCORE, joined_bytes=JOINED)
        self.assertFalse(result["fully_exact_aligned"])
        self.assertEqual(result["exact_aligned_event_count"], 1)
        self.assertEqual(result["event_failure_reasons"], {"CARRIER_INDEX_OUT_OF_RANGE": 1})

    def test_duplicate_runtime_frame_join_is_not_auto_admitted(self):
        result = audit_exact_source_path_v2(events(0, 0), score_bytes=SCORE, joined_bytes=JOINED)
        self.assertFalse(result["fully_exact_aligned"])
        self.assertEqual(result["exact_aligned_event_count"], 0)
        self.assertEqual(
            result["event_failure_reasons"],
            {"MULTIPLE_FUNCTION_EVENTS_SAME_RUNTIME_FRAME": 2},
        )


if __name__ == "__main__":
    unittest.main()
