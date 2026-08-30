from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HFinalFitTests(unittest.TestCase):
    def test_final_fit_remains_closed(self) -> None:
        self.assertFalse(build_stage2h_contract()["full_train_final_fit_started"])


if __name__ == "__main__":
    unittest.main()
