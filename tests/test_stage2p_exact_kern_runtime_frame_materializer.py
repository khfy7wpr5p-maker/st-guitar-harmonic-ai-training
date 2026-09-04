import unittest
from fractions import Fraction

from st_harmonic_training.stage2p_exact_kern_runtime_frame_materializer import (
    Stage2PExactKernMaterializerError,
    _pitch_to_midi,
    _reciprocal_to_quarter_length,
    build_stage2p_contract,
    materialize_exact_kern_runtime_frames,
)


SCORE = b"""**kern\t**kern
*staff2\t*staff1
*clefF4\t*clefG2
*k[b-e-a-]\t*k[b-e-a-]
*M4/4\t*M4/4
*c:\t*c:
=-\t=-
2C 2E- 2G\t4cc
.\t4b-
=2\t=2
2G\t2dd
*-\t*-
"""


class Stage2PExactKernRuntimeFrameMaterializerTests(unittest.TestCase):
    def test_reference_score_materializes_exact_frames(self):
        result = materialize_exact_kern_runtime_frames(SCORE)
        self.assertTrue(result["exact_source_timing_materialized"])
        self.assertEqual(result["kern_spine_count"], 2)
        self.assertEqual(result["data_row_count"], 3)
        self.assertEqual(result["runtime_frame_count"], 3)
        self.assertEqual(result["measure_count"], 2)
        self.assertFalse(result["heuristic_timing_recovery_used"])
        self.assertFalse(result["model_training_started"])
        self.assertFalse(result["production_authority"])

        frames = [row["frame"] for row in result["frames"]]
        self.assertEqual(frames[0]["measure_number"], 1)
        self.assertEqual(frames[0]["start"], {"numerator": 0, "denominator": 1})
        self.assertEqual(frames[0]["end"], {"numerator": 1, "denominator": 1})
        self.assertEqual(
            sorted((e["staff"], e["voice"], e["midi_pitch"]) for e in frames[0]["events"]),
            [(1, 2, 72), (2, 1, 48), (2, 1, 51), (2, 1, 55)],
        )
        self.assertEqual(frames[1]["start"], {"numerator": 1, "denominator": 1})
        self.assertEqual(frames[1]["end"], {"numerator": 2, "denominator": 1})
        self.assertEqual(
            sorted((e["staff"], e["voice"], e["midi_pitch"]) for e in frames[1]["events"]),
            [(1, 2, 70), (2, 1, 48), (2, 1, 51), (2, 1, 55)],
        )
        self.assertEqual(frames[2]["measure_number"], 2)
        self.assertEqual(frames[2]["end"], {"numerator": 2, "denominator": 1})
        self.assertEqual(
            sorted((e["staff"], e["voice"], e["midi_pitch"]) for e in frames[2]["events"]),
            [(1, 2, 74), (2, 1, 55)],
        )

    def test_same_source_bytes_produce_identical_frame_ids(self):
        left = materialize_exact_kern_runtime_frames(SCORE)
        right = materialize_exact_kern_runtime_frames(SCORE)
        self.assertEqual(
            [row["runtime_frame_id"] for row in left["frames"]],
            [row["runtime_frame_id"] for row in right["frames"]],
        )

    def test_source_bytes_scope_frame_identity(self):
        left = materialize_exact_kern_runtime_frames(SCORE)
        changed = SCORE.replace(b"*c:\t*c:\n", b"*C:\t*C:\n")
        right = materialize_exact_kern_runtime_frames(changed)
        self.assertNotEqual(left["source_sha256"], right["source_sha256"])
        self.assertNotEqual(
            left["frames"][0]["runtime_frame_id"],
            right["frames"][0]["runtime_frame_id"],
        )

    def test_reciprocal_durations_are_exact(self):
        self.assertEqual(_reciprocal_to_quarter_length("4", 0), Fraction(1))
        self.assertEqual(_reciprocal_to_quarter_length("2", 1), Fraction(3))
        self.assertEqual(_reciprocal_to_quarter_length("12", 0), Fraction(1, 3))
        self.assertEqual(_reciprocal_to_quarter_length("3%2", 0), Fraction(8, 3))
        self.assertEqual(_reciprocal_to_quarter_length("0", 0), Fraction(8))
        self.assertEqual(_reciprocal_to_quarter_length("00", 0), Fraction(16))

    def test_pitch_mapping_matches_kern_absolute_pitch_semantics(self):
        self.assertEqual(_pitch_to_midi("c", None), 60)
        self.assertEqual(_pitch_to_midi("cc", None), 72)
        self.assertEqual(_pitch_to_midi("C", None), 48)
        self.assertEqual(_pitch_to_midi("B", "-"), 58)
        self.assertEqual(_pitch_to_midi("f", "#"), 66)

    def test_tie_states_are_preserved_in_event_identity(self):
        source = b"""**kern
*staff1
=1
[2c
=2
2c]
*-
"""
        result = materialize_exact_kern_runtime_frames(source)
        frames = [row["frame"] for row in result["frames"]]
        self.assertEqual(frames[0]["events"][0]["tie"], "start")
        self.assertEqual(frames[1]["events"][0]["tie"], "stop")

    def test_null_without_sustain_fails_closed(self):
        source = b"""**kern
*staff1
=1
.
*-
"""
        with self.assertRaises(Stage2PExactKernMaterializerError):
            materialize_exact_kern_runtime_frames(source)

    def test_early_rearticulation_fails_closed(self):
        source = b"""**kern\t**kern
*staff1\t*staff2
=1\t=1
2c\t4C
4d\t4D
*-\t*-
"""
        with self.assertRaises(Stage2PExactKernMaterializerError):
            materialize_exact_kern_runtime_frames(source)

    def test_spine_split_fails_closed(self):
        source = b"""**kern
*staff1
=1
4c
*^
4d\t4e
*-\t*-
"""
        with self.assertRaises(Stage2PExactKernMaterializerError):
            materialize_exact_kern_runtime_frames(source)

    def test_grace_note_fails_closed(self):
        source = b"""**kern
*staff1
=1
8cq
*-
"""
        with self.assertRaises(Stage2PExactKernMaterializerError):
            materialize_exact_kern_runtime_frames(source)

    def test_missing_explicit_staff_fails_closed(self):
        source = b"""**kern
=1
4c
*-
"""
        with self.assertRaises(Stage2PExactKernMaterializerError):
            materialize_exact_kern_runtime_frames(source)

    def test_contract_keeps_model_and_production_closed(self):
        contract = build_stage2p_contract()
        self.assertEqual(contract["runtime_frame_id_role"], "JOIN_KEY_NOT_MODEL_FEATURE")
        self.assertFalse(contract["heuristic_timing_recovery_authorized"])
        self.assertFalse(contract["model_feature_materialization_authorized"])
        self.assertFalse(contract["model_training_started"])
        self.assertFalse(contract["production_authority"])


if __name__ == "__main__":
    unittest.main()
