from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from st_harmonic_training.tavern_gold_candidates import (
    TavernGoldCandidateError,
    build_tavern_gold_candidate_plan,
    build_tavern_gold_candidate_plan_from_file,
    build_tavern_gold_candidate_summary,
    canonical_tavern_gold_candidate_json,
)
from st_harmonic_training.tavern_structure import PINNED_TAVERN_REVISION


class TavernGoldCandidateTests(unittest.TestCase):
    def adjudication(self) -> dict[str, object]:
        return {
            "schema_version": "st-tavern-human-adjudication-v1",
            "source_corpus": "TAVERN",
            "source_revision": PINNED_TAVERN_REVISION,
            "reviewer_type": "HUMAN",
            "reviewer_ref": "reviewer-opaque-001",
            "review_session_id": "session-001",
            "comparison_evidence_sha256": "b6f3e80c98acbdeac964ae47f568bf9a6c7eead6efbc221b47d74cdb56293db4",
            "decisions": [
                {
                    "phrase_key": "Beethoven/B063:00:01",
                    "decision": "SELECT_A",
                    "annotator_A_raw_sha256": "1" * 64,
                    "annotator_B_raw_sha256": "2" * 64,
                },
                {
                    "phrase_key": "Beethoven/B063:00:02",
                    "decision": "PRESERVE_VARIANTS",
                    "annotator_A_raw_sha256": "3" * 64,
                    "annotator_B_raw_sha256": "4" * 64,
                },
                {
                    "phrase_key": "Beethoven/B063:00:03",
                    "decision": "ABSTAIN",
                    "annotator_A_raw_sha256": "5" * 64,
                    "annotator_B_raw_sha256": "6" * 64,
                },
            ],
        }

    def plan(self, data: dict[str, object] | None = None) -> dict[str, object]:
        return build_tavern_gold_candidate_plan(
            data or self.adjudication(),
            artifact_sha256="a" * 64,
            expected_artifact_sha256="a" * 64,
            expected_decision_count=3,
        )

    def test_human_selection_maps_to_candidate_only(self) -> None:
        plan = self.plan()
        by_phrase = {item["phrase_key"]: item for item in plan["candidates"]}
        self.assertEqual(by_phrase["Beethoven/B063:00:01"]["candidate_disposition"], "GOLD_EXPERT_CANDIDATE")
        self.assertEqual(by_phrase["Beethoven/B063:00:01"]["selected_source"], "A")
        self.assertEqual(by_phrase["Beethoven/B063:00:02"]["candidate_disposition"], "GOLD_VARIANT_CANDIDATE")
        self.assertEqual(by_phrase["Beethoven/B063:00:03"]["candidate_disposition"], "QUARANTINE_ABSTAIN")
        self.assertFalse(plan["gold_assignment_authorized"])
        self.assertFalse(plan["training_authorized"])

    def test_confirm_equivalent_requires_explicit_human_decision(self) -> None:
        data = self.adjudication()
        data["decisions"][0]["decision"] = "CONFIRM_EQUIVALENT"
        plan = self.plan(data)
        item = {x["phrase_key"]: x for x in plan["candidates"]}["Beethoven/B063:00:01"]
        self.assertEqual(item["candidate_disposition"], "GOLD_CONSENSUS_CANDIDATE")
        self.assertEqual(item["selected_source"], "A+B_HUMAN_CONFIRMED_EQUIVALENT")

    def test_candidate_summary_contains_no_per_record_rows(self) -> None:
        summary = build_tavern_gold_candidate_summary(self.plan())
        self.assertNotIn("candidates", summary)
        self.assertEqual(summary["teacher_gold_candidate_count"], 2)
        self.assertEqual(summary["quarantined_count"], 1)
        self.assertFalse(summary["gold_assignment_authorized"])

    def test_wrong_artifact_digest_fails_closed(self) -> None:
        with self.assertRaises(TavernGoldCandidateError):
            build_tavern_gold_candidate_plan(
                self.adjudication(),
                artifact_sha256="a" * 64,
                expected_artifact_sha256="b" * 64,
                expected_decision_count=3,
            )

    def test_non_human_reviewer_fails_closed(self) -> None:
        data = self.adjudication()
        data["reviewer_type"] = "AUTO"
        with self.assertRaises(TavernGoldCandidateError):
            self.plan(data)

    def test_duplicate_phrase_fails_closed(self) -> None:
        data = self.adjudication()
        data["decisions"][1]["phrase_key"] = data["decisions"][0]["phrase_key"]
        with self.assertRaises(TavernGoldCandidateError):
            self.plan(data)

    def test_hash_anchor_shape_fails_closed(self) -> None:
        data = self.adjudication()
        data["decisions"][0]["annotator_A_raw_sha256"] = "not-a-hash"
        with self.assertRaises(TavernGoldCandidateError):
            self.plan(data)

    def test_decision_count_tamper_fails_closed(self) -> None:
        with self.assertRaises(TavernGoldCandidateError):
            build_tavern_gold_candidate_plan(
                self.adjudication(),
                artifact_sha256="a" * 64,
                expected_artifact_sha256="a" * 64,
                expected_decision_count=4,
            )

    def test_file_boundary_rejects_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "decisions.json"
            target.write_text(json.dumps(self.adjudication()), encoding="utf-8")
            link = root / "link.json"
            try:
                link.symlink_to(target)
            except OSError:
                self.skipTest("symlink creation unavailable")
            with self.assertRaises(TavernGoldCandidateError):
                build_tavern_gold_candidate_plan_from_file(link)

    def test_canonical_output_is_deterministic(self) -> None:
        left = self.plan()
        right_data = self.adjudication()
        right_data["decisions"] = list(reversed(right_data["decisions"]))
        right = self.plan(right_data)
        self.assertEqual(
            canonical_tavern_gold_candidate_json(left),
            canonical_tavern_gold_candidate_json(right),
        )


if __name__ == "__main__":
    unittest.main()
