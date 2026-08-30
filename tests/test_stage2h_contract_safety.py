from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HContractSafetyTests(unittest.TestCase):
    def test_safety_contract_stays_fail_closed(self) -> None:
        contract = build_stage2h_contract()
        self.assertFalse(contract["production_authority"])
        self.assertFalse(contract["holdout_target_access"])
        self.assertFalse(contract["event_random_split_authorized"])
        self.assertTrue(contract["deterministic_resolver_remains_authoritative"])


if __name__ == "__main__":
    unittest.main()
