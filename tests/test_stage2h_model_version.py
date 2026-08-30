from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HModelVersionTests(unittest.TestCase):
    def test_model_version_is_frozen(self) -> None:
        self.assertEqual(
            build_stage2h_contract()["model_implementation_version"],
            "stage2h-multinomial-nb-v1",
        )


if __name__ == "__main__":
    unittest.main()
