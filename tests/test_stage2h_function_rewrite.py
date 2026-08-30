from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HFunctionRewriteTests(unittest.TestCase):
    def test_function_token_rewrite_is_forbidden(self) -> None:
        self.assertFalse(build_stage2h_contract()["function_token_rewrite_authorized"])


if __name__ == "__main__":
    unittest.main()
