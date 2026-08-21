from __future__ import annotations

import unittest

from st_harmonic_training.tavern_structure import (
    DOCUMENTED_WORKS,
    TavernStructureError,
    analyze_logical_paths,
    build_work_family_manifest,
    canonical_json,
)


class TavernStructureTests(unittest.TestCase):
    def test_undocumented_encoder_c_is_a_blocker(self) -> None:
        report = analyze_logical_paths([
            "Beethoven/B063/Krn/B063_00_01_score.krn",
            "Beethoven/B063/Encodings/Encoder_A/B063_00_01_encoderA.krn",
            "Beethoven/B063/Encodings/Encoder_B/B063_00_01_encoderB.krn",
            "Beethoven/B063/Encodings/Encoder_C/B063_00_02_encoderC.krn",
        ])
        self.assertEqual(report.undocumented_annotator_file_counts, {"Encoder_C": 1})
        self.assertEqual(report.undocumented_only_phrase_keys, 1)
        self.assertIn("UNDOCUMENTED_ANNOTATOR:Encoder_C:1", report.blockers)
        self.assertFalse(report.to_dict()["blanket_teacher_gold_authorized"])

    def test_missing_a_or_b_never_becomes_blanket_gold(self) -> None:
        report = analyze_logical_paths([
            "Beethoven/B063/Krn/B063_00_01_score.krn",
            "Beethoven/B063/Encodings/Encoder_B/B063_00_01_encoderB.krn",
        ])
        self.assertEqual(report.score_b_without_a, 1)
        self.assertEqual(report.complete_score_a_b, 0)
        self.assertIn("INCOMPLETE_SCORE_AB_COVERAGE", report.blockers)
        self.assertFalse(report.to_dict()["blanket_teacher_gold_authorized"])

    def test_analysis_without_score_is_reported(self) -> None:
        report = analyze_logical_paths([
            "Mozart/K025/Encodings/Encoder_A/K025_00_01_encoderA.krn",
            "Mozart/K025/Encodings/Encoder_B/K025_00_01_encoderB.krn",
        ])
        self.assertEqual(report.documented_analysis_without_score, 1)
        self.assertIn("INCOMPLETE_SCORE_AB_COVERAGE", report.blockers)

    def test_annotator_folder_suffix_mismatch_fails_closed(self) -> None:
        with self.assertRaises(TavernStructureError):
            analyze_logical_paths([
                "Beethoven/B063/Encodings/Encoder_A/B063_00_01_encoderB.krn",
            ])

    def test_readme_phrase_count_mismatch_is_explicit(self) -> None:
        report = analyze_logical_paths([
            "Beethoven/B063/Krn/B063_00_01_score.krn",
            "Beethoven/B063/Encodings/Encoder_A/B063_00_01_encoderA.krn",
            "Beethoven/B063/Encodings/Encoder_B/B063_00_01_encoderB.krn",
        ])
        self.assertTrue(
            any(item.startswith("DOCUMENTED_PHRASE_COUNT_MISMATCH:1060!=") for item in report.blockers)
        )

    def test_work_family_manifest_has_exact_documented_27_works(self) -> None:
        revision = "7cc65dc5365603a92376af50ac71491bea7a16ae"
        manifest = build_work_family_manifest(immutable_revision=revision)
        expected_count = sum(len(values) for values in DOCUMENTED_WORKS.values())
        self.assertEqual(expected_count, 27)
        self.assertEqual(manifest["work_family_count"], 27)
        families = manifest["families"]
        self.assertEqual(len({item["canonical_work_id"] for item in families}), 27)
        self.assertEqual(len({item["split_group_id"] for item in families}), 27)
        self.assertTrue(all(item["partition"] == "QUARANTINE" for item in families))
        self.assertTrue(all(item["cross_corpus_dedup_status"] == "PENDING" for item in families))
        self.assertTrue(
            all(item["split_status"] == "WITHHELD_PENDING_CROSS_CORPUS_DEDUP" for item in families)
        )
        self.assertFalse(manifest["training_authorized"])

    def test_work_family_json_is_deterministic(self) -> None:
        revision = "7cc65dc5365603a92376af50ac71491bea7a16ae"
        manifest = build_work_family_manifest(immutable_revision=revision)
        self.assertEqual(canonical_json(manifest), canonical_json(dict(reversed(list(manifest.items())))))


if __name__ == "__main__":
    unittest.main()
