from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HNonTrainTests(unittest.TestCase):
    def test_non_train_annotation_bodies_remain_unmaterialized(self) -> None:
        self.assertFalse(build_stage2h_contract()["non_train_annotation_bodies_materialized"])


if __name__ == "__main__":
    unittest.main()
