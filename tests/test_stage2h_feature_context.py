from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HFeatureContextTests(unittest.TestCase):
    def test_phrase_context_feature_scope_is_explicit(self) -> None:
        self.assertEqual(
            build_stage2h_contract()["feature_scope"],
            "STAGE2B_TRAIN_PHRASE_CONTEXT_FEATURES",
        )


if __name__ == "__main__":
    unittest.main()
