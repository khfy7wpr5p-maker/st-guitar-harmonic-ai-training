from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import FUNCTION_SPECIALIST_TARGET_SHAPE


class Stage2HFunctionShapePinTests(unittest.TestCase):
    def test_function_target_shape_is_onset_event(self) -> None:
        self.assertEqual(FUNCTION_SPECIALIST_TARGET_SHAPE, "ONSET_EVENT")


if __name__ == "__main__":
    unittest.main()
