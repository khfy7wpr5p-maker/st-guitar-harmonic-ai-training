from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import (
    SELECTION_METRIC,
    SELECTION_POLICY,
    build_stage2h_contract,
)


class Stage2HSelectionTests(unittest.TestCase):
    def test_selection_policy_is_frozen_and_train_internal(self) -> None:
        contract = build_stage2h_contract()
        self.assertEqual(SELECTION_METRIC, "POOLED_EVENT_ACCURACY")
        self.assertEqual(SELECTION_POLICY, "MAX_METRIC_THEN_LOWEST_ALPHA")
        self.assertEqual(contract["selection_metric"], SELECTION_METRIC)
        self.assertEqual(contract["selection_policy"], SELECTION_POLICY)
        self.assertEqual(contract["candidate_alphas"], [0.25, 0.5, 1.0, 2.0, 4.0])
        self.assertFalse(contract["holdout_target_access"])


if __name__ == "__main__":
    unittest.main()
