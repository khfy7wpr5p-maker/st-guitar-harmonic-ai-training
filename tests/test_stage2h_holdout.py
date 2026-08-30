from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HHoldoutTests(unittest.TestCase):
    def test_holdout_target_access_remains_false(self) -> None:
        self.assertFalse(build_stage2h_contract()["holdout_target_access"])


if __name__ == "__main__":
    unittest.main()
