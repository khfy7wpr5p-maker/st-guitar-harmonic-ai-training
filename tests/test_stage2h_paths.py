from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HPathCountTests(unittest.TestCase):
    def test_materializable_source_path_count_is_frozen(self) -> None:
        self.assertEqual(
            build_stage2h_contract()["source_stage2g_materializable_source_path_count"],
            363,
        )


if __name__ == "__main__":
    unittest.main()
