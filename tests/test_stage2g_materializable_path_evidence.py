from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Stage2GMaterializablePathEvidenceTests(unittest.TestCase):
    def test_clarification_evidence_is_fail_closed(self) -> None:
        data = json.loads(
            (ROOT / "evidence" / "stage2g_materializable_path_clarification.v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(data["stage2f_onset_carrier_candidate_source_path_count"], 366)
        self.assertEqual(data["stage2g_materializable_source_path_count"], 363)
        self.assertEqual(data["difference_source_path_count"], 3)
        self.assertTrue(data["record_level_all_selected_variants_must_be_candidate"])
        self.assertFalse(data["partial_quarantine_recovery_authorized"])
        self.assertFalse(data["quarantine_policy_relaxed"])
        self.assertFalse(data["non_train_access"])
        self.assertFalse(data["target_invention"])
        self.assertFalse(data["model_training_started"])
        self.assertFalse(data["production_authority"])


if __name__ == "__main__":
    unittest.main()
