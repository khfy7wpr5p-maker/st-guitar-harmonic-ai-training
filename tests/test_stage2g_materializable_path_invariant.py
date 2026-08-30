from __future__ import annotations

import json
from pathlib import Path
import unittest

from st_harmonic_training.stage2g_function_onset_events import (
    EXPECTED_MATERIALIZABLE_SOURCE_PATH_COUNT,
    EXPECTED_ONSET_CANDIDATE_SOURCE_PATH_COUNT,
    build_stage2g_contract,
)


ROOT = Path(__file__).resolve().parents[1]


class Stage2GMaterializablePathInvariantTests(unittest.TestCase):
    def test_stage2f_candidate_and_stage2g_materializable_counts_are_distinct(self) -> None:
        self.assertEqual(EXPECTED_ONSET_CANDIDATE_SOURCE_PATH_COUNT, 366)
        self.assertEqual(EXPECTED_MATERIALIZABLE_SOURCE_PATH_COUNT, 363)
        self.assertLess(
            EXPECTED_MATERIALIZABLE_SOURCE_PATH_COUNT,
            EXPECTED_ONSET_CANDIDATE_SOURCE_PATH_COUNT,
        )

    def test_contract_freezes_materializable_count_without_rewriting_stage2f_count(self) -> None:
        contract = build_stage2g_contract()
        self.assertEqual(contract["onset_carrier_candidate_source_path_count"], 366)
        self.assertEqual(contract["materializable_source_path_count"], 363)

    def test_committed_contract_matches_builder(self) -> None:
        committed = json.loads(
            (ROOT / "evidence" / "stage2g_function_onset_event_contract.v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(committed, build_stage2g_contract())


if __name__ == "__main__":
    unittest.main()
