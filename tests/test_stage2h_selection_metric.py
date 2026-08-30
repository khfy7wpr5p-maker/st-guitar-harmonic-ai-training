from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HSelectionMetricTests(unittest.TestCase):
    def test_selection_metric_is_pooled_event_accuracy(self) -> None:
        self.assertEqual(
            build_stage2h_contract()["selection_metric"],
            "POOLED_EVENT_ACCURACY",
        )


if __name__ == "__main__":
    unittest.main()
