from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HPrivateCountsTests(unittest.TestCase):
    def test_private_aggregate_counts_are_frozen(self) -> None:
        contract = build_stage2h_contract()
        self.assertEqual(contract["source_stage2g_materialized_event_count"], 1854)
        self.assertEqual(contract["source_stage2g_materializable_source_path_count"], 363)
        self.assertEqual(contract["source_stage2g_candidate_record_count"], 355)


if __name__ == "__main__":
    unittest.main()
