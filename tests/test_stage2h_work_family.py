from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HWorkFamilyTests(unittest.TestCase):
    def test_work_family_is_the_grouping_unit(self) -> None:
        contract = build_stage2h_contract()
        self.assertEqual(contract["grouping_unit"], "SPLIT_GROUP_ID_WORK_FAMILY")
        self.assertEqual(contract["fold_source"], "STAGE1E_DEVELOPMENT_FOLD")


if __name__ == "__main__":
    unittest.main()
