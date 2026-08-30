from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HPrivateExternalTests(unittest.TestCase):
    def test_contract_references_private_payload_by_manifest_only(self) -> None:
        contract = build_stage2h_contract()
        self.assertIn("source_stage2g_private_event_manifest_sha256", contract)
        self.assertNotIn("events", contract)
        self.assertNotIn("records", contract)


if __name__ == "__main__":
    unittest.main()
