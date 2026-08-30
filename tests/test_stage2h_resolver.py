from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HResolverTests(unittest.TestCase):
    def test_resolver_remains_authoritative(self) -> None:
        self.assertTrue(build_stage2h_contract()["deterministic_resolver_remains_authoritative"])


if __name__ == "__main__":
    unittest.main()
