from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HNoInferenceTests(unittest.TestCase):
    def test_no_duration_segment_or_token_inference(self) -> None:
        contract = build_stage2h_contract()
        self.assertFalse(contract["duration_inference_authorized"])
        self.assertFalse(contract["segment_boundary_inference_authorized"])
        self.assertFalse(contract["function_token_rewrite_authorized"])


if __name__ == "__main__":
    unittest.main()
