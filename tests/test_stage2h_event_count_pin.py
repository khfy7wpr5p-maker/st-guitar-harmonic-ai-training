from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import EXPECTED_STAGE2G_EVENT_COUNT


class Stage2HEventCountPinTests(unittest.TestCase):
    def test_event_count_pin_is_exact(self) -> None:
        self.assertEqual(EXPECTED_STAGE2G_EVENT_COUNT, 1854)


if __name__ == "__main__":
    unittest.main()
