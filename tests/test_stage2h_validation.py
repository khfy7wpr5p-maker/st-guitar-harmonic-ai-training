from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HValidationTests(unittest.TestCase):
    def test_original_validation_target_access_remains_false(self) -> None:
        self.assertFalse(build_stage2h_contract()["original_validation_target_access"])


if __name__ == "__main__":
    unittest.main()
