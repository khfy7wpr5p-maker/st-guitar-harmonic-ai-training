from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HContractManifestCountTests(unittest.TestCase):
    def test_manifest_and_event_count_are_jointly_frozen(self) -> None:
        contract = build_stage2h_contract()
        self.assertEqual(contract["source_stage2g_materialized_event_count"], 1854)
        self.assertEqual(
            contract["source_stage2g_private_event_manifest_sha256"],
            "d7bbd514ec85b87aee423cae9dce39c74e634ab2f1040fed82af0e25105f255d",
        )


if __name__ == "__main__":
    unittest.main()
