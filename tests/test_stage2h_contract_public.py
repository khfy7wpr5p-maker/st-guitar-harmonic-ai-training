from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HContractPublicTests(unittest.TestCase):
    def test_public_contract_has_no_private_rows(self) -> None:
        contract = build_stage2h_contract()
        self.assertNotIn("events", contract)
        self.assertNotIn("records", contract)
        self.assertNotIn("function_token", repr(contract))


if __name__ == "__main__":
    unittest.main()
