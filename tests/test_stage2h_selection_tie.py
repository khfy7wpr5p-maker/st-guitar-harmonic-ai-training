from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HSelectionTieTests(unittest.TestCase):
    def test_alpha_ties_choose_lowest_candidate(self) -> None:
        self.assertEqual(
            build_stage2h_contract()["selection_policy"],
            "MAX_METRIC_THEN_LOWEST_ALPHA",
        )


if __name__ == "__main__":
    unittest.main()
