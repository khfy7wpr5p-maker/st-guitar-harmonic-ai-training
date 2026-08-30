from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HContractModelTests(unittest.TestCase):
    def test_model_contract_is_frozen(self) -> None:
        contract = build_stage2h_contract()
        self.assertEqual(contract["model_implementation_version"], "stage2h-multinomial-nb-v1")
        self.assertTrue(contract["cv_model_fit_authorized"])
        self.assertFalse(contract["full_train_final_fit_started"])


if __name__ == "__main__":
    unittest.main()
