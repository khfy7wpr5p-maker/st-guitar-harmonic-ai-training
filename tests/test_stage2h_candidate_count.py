from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HCandidateCountTests(unittest.TestCase):
    def test_candidate_record_count_is_frozen(self) -> None:
        self.assertEqual(build_stage2h_contract()["source_stage2g_candidate_record_count"], 355)


if __name__ == "__main__":
    unittest.main()
