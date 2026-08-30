from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HScoreSemanticsTests(unittest.TestCase):
    def test_scores_are_not_probabilities(self) -> None:
        contract = build_stage2h_contract()
        self.assertEqual(contract["score_semantics"], "MODEL_SCORE_NOT_PROBABILITY")


if __name__ == "__main__":
    unittest.main()
