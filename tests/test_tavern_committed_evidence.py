from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TavernCommittedEvidenceTests(unittest.TestCase):
    def load(self, name: str) -> dict[str, object]:
        path = ROOT / "evidence" / "tavern" / name
        return json.loads(path.read_text(encoding="utf-8"))

    def test_structural_evidence_is_bound_and_fail_closed(self) -> None:
        evidence = self.load("stage0h_tavern_structure.v1.json")
        self.assertEqual(
            evidence["raw_archive_sha256"],
            "b95d85bb3f1e5c0f4ea6df772928d247243485abd93153f0550d6be2fba4fc63",
        )
        self.assertEqual(evidence["documented_phrase_count"], 1060)
        self.assertEqual(evidence["observed_unique_phrase_keys"], 1129)
        self.assertIn("UNDOCUMENTED_ANNOTATOR:Encoder_C:61", evidence["blockers"])
        self.assertFalse(evidence["blanket_teacher_gold_authorized"])
        self.assertFalse(evidence["split_assignment_authorized"])
        self.assertFalse(evidence["training_authorized"])

    def test_work_family_evidence_withholds_split_for_all_27_works(self) -> None:
        evidence = self.load("stage0h_tavern_work_families.v1.json")
        self.assertEqual(evidence["work_family_count"], 27)
        self.assertEqual(
            sum(len(values) for values in evidence["families_by_composer"].values()),
            27,
        )
        self.assertEqual(evidence["partition"], "QUARANTINE")
        self.assertEqual(evidence["cross_corpus_dedup_status"], "PENDING")
        self.assertEqual(
            evidence["split_status"],
            "WITHHELD_PENDING_CROSS_CORPUS_DEDUP",
        )
        self.assertFalse(evidence["split_assignment_authorized"])
        self.assertFalse(evidence["training_authorized"])


if __name__ == "__main__":
    unittest.main()
