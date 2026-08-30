from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import EXPECTED_STAGE2G_CANDIDATE_RECORD_COUNT


class Stage2HCandidateRecordPinTests(unittest.TestCase):
    def test_candidate_record_count_pin_is_exact(self) -> None:
        self.assertEqual(EXPECTED_STAGE2G_CANDIDATE_RECORD_COUNT, 355)


if __name__ == "__main__":
    unittest.main()
