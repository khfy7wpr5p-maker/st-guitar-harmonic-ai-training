from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import EXPECTED_STAGE2G_MATERIALIZABLE_SOURCE_PATH_COUNT


class Stage2HPathCountPinTests(unittest.TestCase):
    def test_materializable_path_count_pin_is_exact(self) -> None:
        self.assertEqual(EXPECTED_STAGE2G_MATERIALIZABLE_SOURCE_PATH_COUNT, 363)


if __name__ == "__main__":
    unittest.main()
