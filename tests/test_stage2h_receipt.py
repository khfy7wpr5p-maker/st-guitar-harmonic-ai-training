from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Stage2HReceiptTests(unittest.TestCase):
    def test_stage2g_receipt_is_bounded_and_authority_closed(self) -> None:
        data = json.loads(
            (ROOT / "evidence/stage2h_stage2g_private_summary_receipt.v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(data["materialized_event_count"], 1854)
        self.assertEqual(data["materialized_source_path_count"], 363)
        self.assertEqual(data["onset_carrier_candidate_source_path_count"], 366)
        self.assertEqual(
            data["private_event_manifest_sha256"],
            "d7bbd514ec85b87aee423cae9dce39c74e634ab2f1040fed82af0e25105f255d",
        )
        for field in (
            "non_train_annotation_bodies_materialized",
            "original_validation_target_access",
            "calibration_target_access",
            "holdout_target_access",
            "model_training_started",
            "model_selection_started",
            "full_train_final_fit_started",
            "production_authority",
        ):
            self.assertFalse(data[field])


if __name__ == "__main__":
    unittest.main()
