from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HPhraseSplitTests(unittest.TestCase):
    def test_phrase_random_split_is_forbidden(self) -> None:
        self.assertFalse(build_stage2h_contract()["phrase_random_split_authorized"])


if __name__ == "__main__":
    unittest.main()
