from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import build_stage2h_contract


class Stage2HSourceCorpusTests(unittest.TestCase):
    def test_source_corpus_is_frozen(self) -> None:
        self.assertEqual(build_stage2h_contract()["source_corpus"], "TAVERN_REVIEWED_694")


if __name__ == "__main__":
    unittest.main()
