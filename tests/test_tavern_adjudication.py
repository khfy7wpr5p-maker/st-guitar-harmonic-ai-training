from __future__ import annotations

import copy
import hashlib
import unittest

from st_harmonic_training.tavern_ab_compare import canonical_ab_comparison_json
from st_harmonic_training.tavern_adjudication import (
    TavernAdjudicationError,
    build_tavern_adjudication_gate,
    canonical_adjudication_gate_json,
)
from st_harmonic_training.tavern_structure import PINNED_TAVERN_REVISION


A1 = "1" * 64
B1 = "2" * 64
A2 = "3" * 64
B2 = "4" * 64
A3 = "5" * 64
B3 = "6" * 64


class TavernAdjudicationTests(unittest.TestCase):
    def comparison(self) -> dict[str, object]:
        return {
            "schema_version": "st-tavern-ab-comparison-v1",
            "source_corpus": "TAVERN",
            "source_revision": PINNED_TAVERN_REVISION,
            "comparison_scope": "EVIDENCE_ONLY_NO_SEMANTIC_EQUIVALENCE",
            "pair_count": 3,
            "relation_counts": {
                "BYTE_EXACT": 1,
                "TEXT_DIFFERENT": 1,
                "TEXT_LINE_ENDING_EQUIVALENT": 1,
            },
            "comparisons": [
                {
                    "phrase_key": "Beethoven/B063:00:01",
                    "relation": "BYTE_EXACT",
                    "annotator_A_raw_sha256": A1,
                    "annotator_B_raw_sha256": B1,
                    "annotator_A_canonical_text_sha256": "a" * 64,
                    "annotator_B_canonical_text_sha256": "a" * 64,
                },
                {
                    "phrase_key": "Beethoven/B063:00:02",
                    "relation": "TEXT_LINE_ENDING_EQUIVALENT",
                    "annotator_A_raw_sha256": A2,
                    "annotator_B_raw_sha256": B2,
                    "annotator_A_canonical_text_sha256": "b" * 64,
                    "annotator_B_canonical_text_sha256": "b" * 64,
                },
                {
                    "phrase_key": "Beethoven/B063:00:03",
                    "relation": "TEXT_DIFFERENT",
                    "annotator_A_raw_sha256": A3,
                    "annotator_B_raw_sha256": B3,
                    "annotator_A_canonical_text_sha256": "c" * 64,
                    "annotator_B_canonical_text_sha256": "d" * 64,
                },
            ],
            "adjudication_authorized": False,
            "gold_assignment_authorized": False,
            "partition_assignment_authorized": False,
            "training_authorized": False,
        }

    def comparison_sha(self, comparison: dict[str, object] | None = None) -> str:
        payload = canonical_ab_comparison_json(comparison or self.comparison())
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def human_input(self, decisions: list[dict[str, object]]) -> dict[str, object]:
        return {
            "schema_version": "st-tavern-human-adjudication-v1",
            "source_corpus": "TAVERN",
            "source_revision": PINNED_TAVERN_REVISION,
            "reviewer_type": "HUMAN",
            "reviewer_ref": "reviewer-opaque-001",
            "review_session_id": "session-001",
            "comparison_evidence_sha256": self.comparison_sha(),
            "decisions": decisions,
        }

    def decision(self, phrase: str, decision: str) -> dict[str, object]:
        anchors = {
            "Beethoven/B063:00:01": (A1, B1),
            "Beethoven/B063:00:02": (A2, B2),
            "Beethoven/B063:00:03": (A3, B3),
        }
        a_hash, b_hash = anchors[phrase]
        return {
            "phrase_key": phrase,
            "decision": decision,
            "annotator_A_raw_sha256": a_hash,
            "annotator_B_raw_sha256": b_hash,
        }

    def build_gate(
        self,
        human: dict[str, object],
        comparison: dict[str, object] | None = None,
    ) -> dict[str, object]:
        evidence = comparison or self.comparison()
        return build_tavern_adjudication_gate(
            evidence,
            human,
            expected_comparison_sha256=self.comparison_sha(evidence),
            expected_pair_count=len(evidence["comparisons"]),
        )

    def test_default_gate_rejects_unpinned_comparison(self) -> None:
        with self.assertRaises(TavernAdjudicationError):
            build_tavern_adjudication_gate(self.comparison(), self.human_input([]))

    def test_complete_human_review_is_evidence_only(self) -> None:
        human = self.human_input([
            self.decision("Beethoven/B063:00:01", "CONFIRM_EQUIVALENT"),
            self.decision("Beethoven/B063:00:02", "CONFIRM_EQUIVALENT"),
            self.decision("Beethoven/B063:00:03", "PRESERVE_VARIANTS"),
        ])
        gate = self.build_gate(human)
        self.assertEqual(gate["review_status"], "COMPLETE")
        self.assertEqual(gate["reviewed_count"], 3)
        self.assertEqual(gate["pending_count"], 0)
        self.assertFalse(gate["gold_assignment_authorized"])
        self.assertFalse(gate["partition_assignment_authorized"])
        self.assertFalse(gate["training_authorized"])

    def test_partial_review_remains_incomplete(self) -> None:
        human = self.human_input([
            self.decision("Beethoven/B063:00:03", "ABSTAIN"),
        ])
        gate = self.build_gate(human)
        self.assertEqual(gate["review_status"], "INCOMPLETE")
        self.assertEqual(gate["reviewed_count"], 1)
        self.assertEqual(gate["pending_count"], 2)

    def test_non_human_reviewer_fails_closed(self) -> None:
        human = self.human_input([])
        human["reviewer_type"] = "AUTO"
        with self.assertRaises(TavernAdjudicationError):
            self.build_gate(human)

    def test_wrong_comparison_digest_fails_closed(self) -> None:
        human = self.human_input([])
        human["comparison_evidence_sha256"] = "0" * 64
        with self.assertRaises(TavernAdjudicationError):
            self.build_gate(human)

    def test_premature_comparison_authority_fails_closed(self) -> None:
        comparison = self.comparison()
        comparison["gold_assignment_authorized"] = True
        human = self.human_input([])
        with self.assertRaises(TavernAdjudicationError):
            self.build_gate(human, comparison)

    def test_duplicate_human_decision_fails_closed(self) -> None:
        item = self.decision("Beethoven/B063:00:03", "ABSTAIN")
        human = self.human_input([item, copy.deepcopy(item)])
        with self.assertRaises(TavernAdjudicationError):
            self.build_gate(human)

    def test_unknown_phrase_fails_closed(self) -> None:
        item = {
            "phrase_key": "Mozart/K999:00:01",
            "decision": "ABSTAIN",
            "annotator_A_raw_sha256": A1,
            "annotator_B_raw_sha256": B1,
        }
        with self.assertRaises(TavernAdjudicationError):
            self.build_gate(self.human_input([item]))

    def test_hash_anchor_mismatch_fails_closed(self) -> None:
        item = self.decision("Beethoven/B063:00:03", "SELECT_A")
        item["annotator_A_raw_sha256"] = "f" * 64
        with self.assertRaises(TavernAdjudicationError):
            self.build_gate(self.human_input([item]))

    def test_text_different_cannot_be_confirmed_equivalent(self) -> None:
        item = self.decision("Beethoven/B063:00:03", "CONFIRM_EQUIVALENT")
        with self.assertRaises(TavernAdjudicationError):
            self.build_gate(self.human_input([item]))

    def test_source_selection_only_applies_to_text_different(self) -> None:
        item = self.decision("Beethoven/B063:00:01", "SELECT_A")
        with self.assertRaises(TavernAdjudicationError):
            self.build_gate(self.human_input([item]))

    def test_text_different_selection_is_still_not_gold(self) -> None:
        item = self.decision("Beethoven/B063:00:03", "SELECT_B")
        gate = self.build_gate(self.human_input([item]))
        self.assertEqual(gate["decision_counts"], {"SELECT_B": 1})
        self.assertFalse(gate["gold_assignment_authorized"])
        self.assertFalse(gate["training_authorized"])

    def test_ambiguous_and_abstain_are_preserved(self) -> None:
        human = self.human_input([
            self.decision("Beethoven/B063:00:01", "AMBIGUOUS"),
            self.decision("Beethoven/B063:00:03", "ABSTAIN"),
        ])
        gate = self.build_gate(human)
        self.assertEqual(gate["decision_counts"], {"ABSTAIN": 1, "AMBIGUOUS": 1})

    def test_relation_count_tamper_fails_closed(self) -> None:
        comparison = self.comparison()
        comparison["relation_counts"] = {"BYTE_EXACT": 3}
        human = self.human_input([])
        with self.assertRaises(TavernAdjudicationError):
            self.build_gate(human, comparison)

    def test_output_contains_no_raw_annotation_text(self) -> None:
        item = self.decision("Beethoven/B063:00:03", "PRESERVE_VARIANTS")
        gate = self.build_gate(self.human_input([item]))
        record = gate["decisions"][0]
        self.assertEqual(
            set(record),
            {
                "phrase_key",
                "decision",
                "comparison_relation",
                "annotator_A_raw_sha256",
                "annotator_B_raw_sha256",
            },
        )

    def test_canonical_gate_json_is_deterministic(self) -> None:
        left_human = self.human_input([
            self.decision("Beethoven/B063:00:03", "PRESERVE_VARIANTS"),
            self.decision("Beethoven/B063:00:01", "CONFIRM_EQUIVALENT"),
        ])
        right_human = self.human_input(list(reversed(left_human["decisions"])))
        left = self.build_gate(left_human)
        right = self.build_gate(right_human)
        self.assertEqual(canonical_adjudication_gate_json(left), canonical_adjudication_gate_json(right))


if __name__ == "__main__":
    unittest.main()
