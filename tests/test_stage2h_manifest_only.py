from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HManifestOnlyTests(unittest.TestCase):
    def test_public_contract_contains_manifest_not_private_rows(self) -> None:
        contract = build_stage2h_contract()
        self.assertIn("source_stage2g_private_event_manifest_sha256", contract)
        self.assertNotIn("private_events", contract)
        self.assertNotIn("function_targets", contract)


if __name__ == "__main__":
    unittest.main()
