from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HContractRuntimeTests(unittest.TestCase):
    def test_runtime_contract_uses_train_private_inputs_only(self) -> None:
        contract = build_stage2h_contract()
        self.assertEqual(contract["eligible_original_partition"], "TRAIN")
        self.assertEqual(contract["feature_scope"], "STAGE2B_TRAIN_PHRASE_CONTEXT_FEATURES")
        self.assertEqual(contract["event_identity_scope"], "STAGE2G_TRAIN_FUNCTION_ONSET_EVENTS")


if __name__ == "__main__":
    unittest.main()
