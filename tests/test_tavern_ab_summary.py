from __future__ import annotations

import json
from pathlib import Path
import re
import unittest

from st_harmonic_training.tavern_structure import (
    PINNED_TAVERN_RAW_SHA256,
    PINNED_TAVERN_REVISION,
)


SUMMARY_PATH = Path("evidence/tavern/stage0l_tavern_ab_comparison_summary.v1.json")
PHRASE_GATE_PATH = Path("evidence/tavern/stage0k_tavern_phrase_gate.v1.json")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ALLOWED_RELATIONS = {
    "BYTE_EXACT",
    "TEXT_LINE_ENDING_EQUIVALENT",
    "TEXT_DIFFERENT",
}


class TavernABSummaryTests(unittest.TestCase):
    def load_summary(self) -> dict[str, object]:
        return json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))

    def test_summary_is_bound_to_pinned_real_archive_and_revision(self) -> None:
        summary = self.load_summary()
        self.assertEqual(summary["source_corpus"], "TAVERN")
        self.assertEqual(summary["source_revision"], PINNED_TAVERN_REVISION)
        self.assertEqual(summary["raw_archive_sha256"], PINNED_TAVERN_RAW_SHA256)
        self.assertTrue(SHA256_RE.fullmatch(summary["full_evidence_sha256"]))
        self.assertTrue(SHA256_RE.fullmatch(summary["artifact_archive_sha256"]))

    def test_real_pair_count_matches_stage0k_queue(self) -> None:
        summary = self.load_summary()
        phrase_gate = json.loads(PHRASE_GATE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(summary["pair_count"], phrase_gate["teacher_gold_candidate_count"])
        self.assertEqual(summary["pair_count"], 937)

    def test_relation_counts_are_closed_and_complete(self) -> None:
        summary = self.load_summary()
        relations = summary["relation_counts"]
        self.assertEqual(set(relations), ALLOWED_RELATIONS)
        self.assertEqual(sum(relations.values()), summary["pair_count"])
        self.assertEqual(relations["BYTE_EXACT"], 50)
        self.assertEqual(relations["TEXT_LINE_ENDING_EQUIVALENT"], 5)
        self.assertEqual(relations["TEXT_DIFFERENT"], 882)

    def test_summary_never_promotes_comparison_to_authority(self) -> None:
        summary = self.load_summary()
        self.assertEqual(summary["comparison_scope"], "EVIDENCE_ONLY_NO_SEMANTIC_EQUIVALENCE")
        self.assertFalse(summary["raw_annotation_text_committed"])
        self.assertFalse(summary["adjudication_authorized"])
        self.assertFalse(summary["gold_assignment_authorized"])
        self.assertFalse(summary["partition_assignment_authorized"])
        self.assertFalse(summary["training_authorized"])

    def test_sizes_match_independently_verified_artifact_shape(self) -> None:
        summary = self.load_summary()
        self.assertEqual(summary["full_evidence_size_bytes"], 426818)
        self.assertEqual(summary["artifact_archive_size_bytes"], 99450)
        self.assertLess(summary["full_evidence_size_bytes"], 1_048_576)


if __name__ == "__main__":
    unittest.main()
