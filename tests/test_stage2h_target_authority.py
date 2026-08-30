from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HTargetAuthorityTests(unittest.TestCase):
    def test_target_shape_remains_human_function_onset_event(self) -> None:
        contract = build_stage2h_contract()
        self.assertEqual(contract["function_specialist_target_shape"], "ONSET_EVENT")
        self.assertFalse(contract["function_token_rewrite_authorized"])


if __name__ == "__main__":
    unittest.main()
