from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HContractPrivacyTests(unittest.TestCase):
    def test_contract_contains_no_private_target_values(self) -> None:
        contract = build_stage2h_contract()
        rendered = repr(contract)
        self.assertNotIn("function_token", rendered)
        self.assertNotIn("phrase_key", rendered)
        self.assertNotIn("carrier_event_id", rendered)
        self.assertNotIn("source_annotation_sha256", rendered)


if __name__ == "__main__":
    unittest.main()
