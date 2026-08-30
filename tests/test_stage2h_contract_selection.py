from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HContractSelectionTests(unittest.TestCase):
    def test_selection_contract_is_frozen(self) -> None:
        contract = build_stage2h_contract()
        self.assertEqual(contract["selection_metric"], "POOLED_EVENT_ACCURACY")
        self.assertEqual(contract["selection_policy"], "MAX_METRIC_THEN_LOWEST_ALPHA")
        self.assertEqual(contract["candidate_alphas"], [0.25, 0.5, 1.0, 2.0, 4.0])


if __name__ == "__main__":
    unittest.main()
