from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HContractFoldTests(unittest.TestCase):
    def test_fold_contract_is_stage1e_three_fold(self) -> None:
        contract = build_stage2h_contract()
        self.assertEqual(contract["fold_count"], 3)
        self.assertEqual(contract["fold_source"], "STAGE1E_DEVELOPMENT_FOLD")


if __name__ == "__main__":
    unittest.main()
