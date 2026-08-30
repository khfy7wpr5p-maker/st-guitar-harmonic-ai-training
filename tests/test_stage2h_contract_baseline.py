from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import SELECTION_METRIC


class Stage2HContractBaselineTests(unittest.TestCase):
    def test_selection_metric_is_event_accuracy(self) -> None:
        self.assertEqual(SELECTION_METRIC, "POOLED_EVENT_ACCURACY")


if __name__ == "__main__":
    unittest.main()
