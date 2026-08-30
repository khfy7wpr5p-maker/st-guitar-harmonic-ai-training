from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HContractTrainOnlyTests(unittest.TestCase):
    def test_contract_is_train_only(self) -> None:
        contract = build_stage2h_contract()
        self.assertEqual(contract["eligible_original_partition"], "TRAIN")
        self.assertFalse(contract["original_validation_target_access"])
        self.assertFalse(contract["calibration_target_access"])
        self.assertFalse(contract["holdout_target_access"])


if __name__ == "__main__":
    unittest.main()
