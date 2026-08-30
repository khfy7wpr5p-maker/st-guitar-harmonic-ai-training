from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HGroupingTests(unittest.TestCase):
    def test_grouping_is_work_family(self) -> None:
        contract = build_stage2h_contract()
        self.assertEqual(contract["grouping_unit"], "SPLIT_GROUP_ID_WORK_FAMILY")
        self.assertFalse(contract["event_random_split_authorized"])
        self.assertFalse(contract["phrase_random_split_authorized"])


if __name__ == "__main__":
    unittest.main()
