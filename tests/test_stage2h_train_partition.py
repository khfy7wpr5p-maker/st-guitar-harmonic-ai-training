from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HTrainPartitionTests(unittest.TestCase):
    def test_only_train_partition_is_eligible(self) -> None:
        self.assertEqual(build_stage2h_contract()["eligible_original_partition"], "TRAIN")


if __name__ == "__main__":
    unittest.main()
