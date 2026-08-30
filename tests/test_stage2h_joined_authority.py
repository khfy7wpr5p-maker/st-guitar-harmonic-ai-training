from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HJoinedAuthorityTests(unittest.TestCase):
    def test_joined_harmonic_labels_are_not_target_authority(self) -> None:
        self.assertFalse(build_stage2h_contract()["joined_harmonic_labels_authoritative"])


if __name__ == "__main__":
    unittest.main()
