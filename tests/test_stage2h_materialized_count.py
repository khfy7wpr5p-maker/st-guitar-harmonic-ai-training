from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HMaterializedCountTests(unittest.TestCase):
    def test_materialized_event_count_is_frozen(self) -> None:
        self.assertEqual(build_stage2h_contract()["source_stage2g_materialized_event_count"], 1854)


if __name__ == "__main__":
    unittest.main()
