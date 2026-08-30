from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HFeatureScopeTests(unittest.TestCase):
    def test_feature_scope_reuses_train_phrase_context_only(self) -> None:
        contract = build_stage2h_contract()
        self.assertEqual(contract["feature_scope"], "STAGE2B_TRAIN_PHRASE_CONTEXT_FEATURES")
        self.assertEqual(contract["event_identity_scope"], "STAGE2G_TRAIN_FUNCTION_ONSET_EVENTS")


if __name__ == "__main__":
    unittest.main()
