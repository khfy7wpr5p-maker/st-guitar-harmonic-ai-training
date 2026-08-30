from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HFoldSourceTests(unittest.TestCase):
    def test_fold_source_is_stage1e(self) -> None:
        self.assertEqual(build_stage2h_contract()["fold_source"], "STAGE1E_DEVELOPMENT_FOLD")


if __name__ == "__main__":
    unittest.main()
