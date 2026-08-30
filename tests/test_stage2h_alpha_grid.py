from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HAlphaGridTests(unittest.TestCase):
    def test_alpha_grid_matches_frozen_stage2c_candidates(self) -> None:
        self.assertEqual(
            build_stage2h_contract()["candidate_alphas"],
            [0.25, 0.5, 1.0, 2.0, 4.0],
        )


if __name__ == "__main__":
    unittest.main()
