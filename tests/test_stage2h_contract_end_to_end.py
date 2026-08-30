from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HContractEndToEndTests(unittest.TestCase):
    def test_end_to_end_boundaries(self) -> None:
        contract = build_stage2h_contract()
        self.assertEqual(contract["function_specialist_target_shape"], "ONSET_EVENT")
        self.assertEqual(contract["eligible_original_partition"], "TRAIN")
        self.assertTrue(contract["cv_model_fit_authorized"])
        self.assertFalse(contract["full_train_final_fit_started"])
        self.assertFalse(contract["production_authority"])


if __name__ == "__main__":
    unittest.main()
