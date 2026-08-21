from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from st_harmonic_training.tavern_phrase_gate import (
    TavernPhraseGateError,
    build_tavern_phrase_gate,
    canonical_phrase_gate_json,
)


STRUCTURE_PATH = Path("evidence/tavern/stage0i_tavern_structure.v1.json")
LINEAGE_PATH = Path("evidence/tavern/stage0j_tavern_lineage.v1.json")


class TavernPhraseGateTests(unittest.TestCase):
    def load_inputs(self) -> tuple[dict[str, object], dict[str, object]]:
        structure = json.loads(STRUCTURE_PATH.read_text(encoding="utf-8"))
        lineage = json.loads(LINEAGE_PATH.read_text(encoding="utf-8"))
        return structure, lineage

    def test_real_evidence_is_partitioned_into_review_queues_without_promotion(self) -> None:
        structure, lineage = self.load_inputs()
        gate = build_tavern_phrase_gate(structure, lineage)
        self.assertEqual(gate["observed_phrase_count"], 1129)
        self.assertEqual(gate["teacher_gold_candidate_count"], 937)
        self.assertEqual(gate["single_human_review_candidate_count"], 160)
        self.assertEqual(gate["hard_blocked_phrase_count"], 32)
        self.assertIsNone(gate["queues"]["human_pair_adjudication"]["gold_tier_assigned"])
        self.assertFalse(gate["gold_assignment_authorized"])
        self.assertFalse(gate["partition_assignment_authorized"])
        self.assertFalse(gate["training_authorized"])

    def test_pair_complete_does_not_become_gold_automatically(self) -> None:
        structure, lineage = self.load_inputs()
        gate = build_tavern_phrase_gate(structure, lineage)
        pair = gate["queues"]["human_pair_adjudication"]
        self.assertEqual(pair["decision"], "A_B_CONTENT_COMPARISON_REQUIRED")
        self.assertIsNone(pair["gold_tier_assigned"])

    def test_single_b_does_not_become_teacher_gold_automatically(self) -> None:
        structure, lineage = self.load_inputs()
        gate = build_tavern_phrase_gate(structure, lineage)
        single = gate["queues"]["single_human_review"]
        self.assertEqual(single["count"], 160)
        self.assertEqual(single["decision"], "SINGLE_HUMAN_PROVENANCE_REVIEW_REQUIRED")
        self.assertIsNone(single["gold_tier_assigned"])

    def test_status_total_tamper_fails_closed(self) -> None:
        structure, lineage = self.load_inputs()
        structure["phrase_status_counts"]["PAIR_COMPLETE"] += 1
        with self.assertRaises(TavernPhraseGateError):
            build_tavern_phrase_gate(structure, lineage)

    def test_unknown_status_fails_closed(self) -> None:
        structure, lineage = self.load_inputs()
        structure["phrase_status_counts"]["UNKNOWN"] = 1
        structure["observed_counts"]["phrase_keys"] += 1
        with self.assertRaises(TavernPhraseGateError):
            build_tavern_phrase_gate(structure, lineage)

    def test_premature_lineage_partition_authorization_fails_closed(self) -> None:
        structure, lineage = self.load_inputs()
        lineage["partition_assignment_authorized"] = True
        with self.assertRaises(TavernPhraseGateError):
            build_tavern_phrase_gate(structure, lineage)

    def test_premature_training_authorization_fails_closed(self) -> None:
        structure, lineage = self.load_inputs()
        structure["training_authorized"] = True
        with self.assertRaises(TavernPhraseGateError):
            build_tavern_phrase_gate(structure, lineage)

    def test_lineage_work_count_tamper_fails_closed(self) -> None:
        structure, lineage = self.load_inputs()
        lineage["work_family_count"] = 26
        with self.assertRaises(TavernPhraseGateError):
            build_tavern_phrase_gate(structure, lineage)

    def test_count_preserving_lineage_identity_tamper_fails_closed(self) -> None:
        structure, lineage = self.load_inputs()
        lineage["work_families"][0]["source_work_id"] = "TEST/NOT_A_DOCUMENTED_WORK"
        with self.assertRaises(TavernPhraseGateError):
            build_tavern_phrase_gate(structure, lineage)

    def test_canonical_json_is_deterministic(self) -> None:
        structure, lineage = self.load_inputs()
        left = canonical_phrase_gate_json(build_tavern_phrase_gate(structure, lineage))
        right = canonical_phrase_gate_json(
            build_tavern_phrase_gate(copy.deepcopy(structure), copy.deepcopy(lineage))
        )
        self.assertEqual(left, right)


if __name__ == "__main__":
    unittest.main()
