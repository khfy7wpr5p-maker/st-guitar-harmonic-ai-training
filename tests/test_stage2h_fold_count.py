from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HFoldCountTests(unittest.TestCase):
    def test_fold_count_is_three(self) -> None:
        self.assertEqual(build_stage2h_contract()["fold_count"], 3)


if __name__ == "__main__":
    unittest.main()
