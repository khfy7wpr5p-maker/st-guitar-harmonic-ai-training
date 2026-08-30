from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import SCORE_SEMANTICS


class Stage2HScoreProbabilityTests(unittest.TestCase):
    def test_score_semantics_do_not_claim_probability(self) -> None:
        self.assertEqual(SCORE_SEMANTICS, "MODEL_SCORE_NOT_PROBABILITY")


if __name__ == "__main__":
    unittest.main()
