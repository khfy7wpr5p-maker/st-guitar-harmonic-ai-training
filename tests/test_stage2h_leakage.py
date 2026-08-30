from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HLeakageTests(unittest.TestCase):
    def test_cross_work_family_leakage_is_forbidden(self) -> None:
        self.assertFalse(build_stage2h_contract()["cross_work_family_leakage_authorized"])


if __name__ == "__main__":
    unittest.main()
