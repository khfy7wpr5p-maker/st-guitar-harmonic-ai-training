from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HEventIdentityTests(unittest.TestCase):
    def test_event_identity_scope_is_stage2g_train_events(self) -> None:
        self.assertEqual(
            build_stage2h_contract()["event_identity_scope"],
            "STAGE2G_TRAIN_FUNCTION_ONSET_EVENTS",
        )


if __name__ == "__main__":
    unittest.main()
