from __future__ import annotations

import copy
import hashlib
import json
import tempfile
from pathlib import Path
import unittest

from st_harmonic_training.normalization import NORMALIZATION_VERSION
from st_harmonic_training.tavern_gold_materialization import (
    TavernGoldMaterializationError,
    build_tavern_gold_materialization,
    build_tavern_gold_materialization_from_file,
    canonical_tavern_gold_materialization_json,
)
from st_harmonic_training.tavern_structure import PINNED_TAVERN_REVISION
from st_harmonic_training.tavern_adjudication import PINNED_TAVERN_AB_COMPARISON_SHA256

A = "1" * 64
B = "2" * 64


class TavernGoldMaterializationTests(unittest.TestCase):
    def payload(self, decision: str = "SELECT_B") -> dict[str, object]:
        return {
            "schema_version": "st-tavern-human-adjudication-v1",
            "source_corpus": "TAVERN",
            "source_revision": PINNED_TAVERN_REVISION,
            "reviewer_type": "HUMAN",
            "reviewer_ref": "reviewer-opaque",
            "review_session_id": "session",
            "comparison_evidence_sha256": PINNED_TAVERN_AB_COMPARISON_SHA256,
            "decisions": [{
                "phrase_key": "Beethoven/B063:00:01",
                "decision": decision,
                "annotator_A_raw_sha256": A,
                "annotator_B_raw_sha256": B,
            }],
        }

    def build(self, decision: str = "SELECT_B") -> dict[str, object]:
        return build_tavern_gold_materialization(
            self.payload(decision), artifact_sha256="a" * 64,
            expected_artifact_sha256="a" * 64, expected_count=1,
        )

    def test_select_b_becomes_hash_bound_expert_gold(self) -> None:
        plan = self.build("SELECT_B")
        record = plan["records"][0]
        self.assertEqual(record["gold_tier"], "GOLD_EXPERT")
        self.assertEqual(record["annotation_kind"], "HUMAN_EXPERT")
        self.assertEqual(record["selected_sources"], ["B"])
        self.assertEqual(record["selected_raw_label_sha256"], [B])
        self.assertEqual(record["normalization_version"], NORMALIZATION_VERSION)
        self.assertFalse(record["training_eligible"])
        self.assertTrue(plan["gold_assignment_authorized"])
        self.assertFalse(plan["training_authorized"])

    def test_variants_preserve_both_human_sources(self) -> None:
        record = self.build("PRESERVE_VARIANTS")["records"][0]
        self.assertEqual(record["gold_tier"], "GOLD_VARIANT")
        self.assertEqual(record["selected_sources"], ["A", "B"])
        self.assertEqual(record["selected_raw_label_sha256"], [A, B])
        self.assertEqual(record["annotator_count"], 2)

    def test_ambiguous_is_quarantined(self) -> None:
        record = self.build("AMBIGUOUS")["records"][0]
        self.assertEqual(record["gold_tier"], "QUARANTINE")
        self.assertFalse(record["training_eligible"])

    def test_non_human_reviewer_fails_closed(self) -> None:
        payload = self.payload()
        payload["reviewer_type"] = "AUTO"
        with self.assertRaises(TavernGoldMaterializationError):
            build_tavern_gold_materialization(
                payload, artifact_sha256="a" * 64,
                expected_artifact_sha256="a" * 64, expected_count=1,
            )

    def test_artifact_digest_mismatch_fails_closed(self) -> None:
        with self.assertRaises(TavernGoldMaterializationError):
            build_tavern_gold_materialization(
                self.payload(), artifact_sha256="a" * 64,
                expected_artifact_sha256="b" * 64, expected_count=1,
            )

    def test_duplicate_phrase_fails_closed(self) -> None:
        payload = self.payload()
        payload["decisions"].append(copy.deepcopy(payload["decisions"][0]))
        with self.assertRaises(TavernGoldMaterializationError):
            build_tavern_gold_materialization(
                payload, artifact_sha256="a" * 64,
                expected_artifact_sha256="a" * 64, expected_count=2,
            )

    def test_symlink_file_input_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            target = root / "input.json"
            target.write_text(json.dumps(self.payload()), encoding="utf-8")
            link = root / "link.json"
            link.symlink_to(target)
            with self.assertRaises(TavernGoldMaterializationError):
                build_tavern_gold_materialization_from_file(link)

    def test_canonical_output_is_deterministic(self) -> None:
        left = self.build("SELECT_A")
        right = self.build("SELECT_A")
        self.assertEqual(
            canonical_tavern_gold_materialization_json(left),
            canonical_tavern_gold_materialization_json(right),
        )

    def test_output_contains_no_raw_annotation_text(self) -> None:
        text = canonical_tavern_gold_materialization_json(self.build())
        self.assertNotIn("raw_source_label", text)
        self.assertIn(B, text)


if __name__ == "__main__":
    unittest.main()
