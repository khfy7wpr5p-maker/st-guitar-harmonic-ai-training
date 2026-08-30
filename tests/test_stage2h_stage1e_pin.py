from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HStage1EPinTests(unittest.TestCase):
    def test_stage1e_group_plan_pin_is_frozen(self) -> None:
        self.assertEqual(
            build_stage2h_contract()["source_stage1e_group_plan_manifest_sha256"],
            "ae15ed507247548907815f8ee1a5586f9fa2384a32d5102e887ddedff52e1a4c",
        )


if __name__ == "__main__":
    unittest.main()
