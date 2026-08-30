from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HContractAuthorityTests(unittest.TestCase):
    def test_authority_boundary_is_closed(self) -> None:
        contract = build_stage2h_contract()
        self.assertTrue(contract["cv_model_fit_authorized"])
        self.assertFalse(contract["full_train_final_fit_started"])
        self.assertFalse(contract["production_authority"])
        self.assertTrue(contract["deterministic_resolver_remains_authoritative"])


if __name__ == "__main__":
    unittest.main()
