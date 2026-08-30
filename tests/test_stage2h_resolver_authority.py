from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HResolverAuthorityTests(unittest.TestCase):
    def test_deterministic_resolver_remains_authoritative(self) -> None:
        contract = build_stage2h_contract()
        self.assertTrue(contract["deterministic_resolver_remains_authoritative"])
        self.assertFalse(contract["production_authority"])


if __name__ == "__main__":
    unittest.main()
