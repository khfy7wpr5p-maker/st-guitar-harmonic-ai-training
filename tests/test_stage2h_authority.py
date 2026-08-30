from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HAuthorityTests(unittest.TestCase):
    def test_production_authority_remains_false(self) -> None:
        self.assertFalse(build_stage2h_contract()["production_authority"])


if __name__ == "__main__":
    unittest.main()
