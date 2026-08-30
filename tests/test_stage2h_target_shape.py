from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HTargetShapeTests(unittest.TestCase):
    def test_function_target_remains_onset_event(self) -> None:
        contract = build_stage2h_contract()
        self.assertEqual(contract["function_specialist_target_shape"], "ONSET_EVENT")
        self.assertFalse(contract["duration_inference_authorized"])
        self.assertFalse(contract["segment_boundary_inference_authorized"])
        self.assertFalse(contract["function_token_rewrite_authorized"])


if __name__ == "__main__":
    unittest.main()
