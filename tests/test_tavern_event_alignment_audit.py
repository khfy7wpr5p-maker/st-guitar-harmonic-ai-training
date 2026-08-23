from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from st_harmonic_training.tavern_event_alignment_audit import (
    ALIGNMENT_SCHEMA,
    SUMMARY_SCHEMA,
    TavernEventAlignmentError,
    build_tavern_event_alignment_audit,
    build_tavern_event_alignment_summary,
    canonical_tavern_event_alignment_json,
)
from st_harmonic_training.tavern_structure import PINNED_TAVERN_REVISION


class TavernEventAlignmentAuditTests(unittest.TestCase):
    def _encoder(self, second_duration: str = "2") -> bytes:
        return (
            "**chords\t**function\n"
            "*C:\t*C:\n"
            "1I\tT\n"
            f"{second_duration}V\tD\n"
            "2I\tT\n"
            "*-\t*-\n"
        ).encode("utf-8")

    def _joined(self, second_duration: str = "2", roman: str = "V") -> bytes:
        return (
            "**harm\t**kern\t**kern\n"
            "*C:\t*C:\t*C:\n"
            "1I\t4c\t4e\n"
            f"{second_duration}{roman}\t2d\t2f\n"
            "2I\t2e\t2g\n"
            "*-\t*-\t*-\n"
        ).encode("utf-8")

    def _fixture(self, *, joined_duration: str = "2", joined_roman: str = "V"):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        archive = root / "tavern.zip"
        encoder = self._encoder()
        joined = self._joined(joined_duration, joined_roman)
        with zipfile.ZipFile(archive, "w") as handle:
            handle.writestr(
                "TAVERN-test/Beethoven/B063/Encodings/Encoder_B/"
                "B063_00_01_encoderB.krn",
                encoder,
            )
            handle.writestr(
                "TAVERN-test/Beethoven/B063/Joined/B063_00_01a_b.krn",
                joined,
            )
        archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
        decision = {
            "schema_version": "st-tavern-human-adjudication-v1",
            "source_corpus": "TAVERN",
            "source_revision": PINNED_TAVERN_REVISION,
            "reviewer_type": "HUMAN",
            "decisions": [
                {
                    "phrase_key": "Beethoven/B063:00:01",
                    "decision": "SELECT_B",
                    "annotator_A_raw_sha256": "0" * 64,
                    "annotator_B_raw_sha256": hashlib.sha256(encoder).hexdigest(),
                }
            ],
        }
        decision_sha = hashlib.sha256(
            json.dumps(decision, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return temp, archive, archive_sha, decision, decision_sha

    def _build(self, *, joined_duration: str = "2", joined_roman: str = "V"):
        temp, archive, archive_sha, decision, decision_sha = self._fixture(
            joined_duration=joined_duration, joined_roman=joined_roman
        )
        self.addCleanup(temp.cleanup)
        return build_tavern_event_alignment_audit(
            decision,
            decision_artifact_sha256=decision_sha,
            archive_path=archive,
            expected_decision_sha256=decision_sha,
            expected_archive_sha256=archive_sha,
            expected_record_count=1,
            expected_selected_target_count=1,
            expected_alignment_manifest_sha256=None,
        )

    def test_exact_reciprocal_sequence_is_candidate(self):
        result = self._build()
        self.assertEqual(result["schema_version"], ALIGNMENT_SCHEMA)
        self.assertEqual(result["event_alignment_candidate_count"], 1)
        self.assertEqual(result["expert_event_alignment_candidate_count"], 1)
        self.assertEqual(result["quarantine_record_count"], 0)
        self.assertEqual(
            result["records"][0]["record_status"],
            "EXPERT_EVENT_ALIGNMENT_CANDIDATE",
        )
        self.assertFalse(result["joined_labels_authoritative"])
        self.assertFalse(result["joined_labels_used_as_targets"])
        self.assertFalse(result["event_target_materialization_authorized"])
        self.assertFalse(result["training_authorized"])
        self.assertFalse(result["production_authority"])

    def test_label_transform_does_not_become_authoritative_target(self):
        result = self._build(joined_roman="Vb")
        path = result["records"][0]["selected_paths"][0]
        self.assertTrue(path["duration_sequence_exact"])
        self.assertFalse(path["joined_label_sequence_exact"])
        self.assertEqual(result["event_alignment_candidate_count"], 1)
        self.assertFalse(result["joined_labels_authoritative"])
        self.assertFalse(result["joined_labels_used_as_targets"])

    def test_reciprocal_sequence_mismatch_quarantines_record(self):
        result = self._build(joined_duration="4")
        self.assertEqual(result["event_alignment_candidate_count"], 0)
        self.assertEqual(result["quarantine_record_count"], 1)
        record = result["records"][0]
        self.assertEqual(record["record_status"], "QUARANTINE")
        self.assertIn(
            "B_RECIPROCAL_EVENT_SEQUENCE_MISMATCH",
            record["quarantine_reasons"],
        )

    def test_selected_encoder_hash_tamper_fails_closed(self):
        temp, archive, archive_sha, decision, decision_sha = self._fixture()
        self.addCleanup(temp.cleanup)
        tampered = copy.deepcopy(decision)
        tampered["decisions"][0]["annotator_B_raw_sha256"] = "f" * 64
        with self.assertRaises(TavernEventAlignmentError):
            build_tavern_event_alignment_audit(
                tampered,
                decision_artifact_sha256=decision_sha,
                archive_path=archive,
                expected_decision_sha256=decision_sha,
                expected_archive_sha256=archive_sha,
                expected_record_count=1,
                expected_selected_target_count=1,
                expected_alignment_manifest_sha256=None,
            )

    def test_variant_requires_both_selected_paths(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        archive = root / "tavern.zip"
        encoder_a = self._encoder()
        encoder_b = self._encoder()
        joined_a = self._joined()
        joined_b = self._joined("4")
        with zipfile.ZipFile(archive, "w") as handle:
            handle.writestr(
                "TAVERN-test/Beethoven/B063/Encodings/Encoder_A/"
                "B063_00_01_encoderA.krn",
                encoder_a,
            )
            handle.writestr(
                "TAVERN-test/Beethoven/B063/Encodings/Encoder_B/"
                "B063_00_01_encoderB.krn",
                encoder_b,
            )
            handle.writestr(
                "TAVERN-test/Beethoven/B063/Joined/B063_00_01a_a.krn",
                joined_a,
            )
            handle.writestr(
                "TAVERN-test/Beethoven/B063/Joined/B063_00_01a_b.krn",
                joined_b,
            )
        archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
        decision = {
            "schema_version": "st-tavern-human-adjudication-v1",
            "source_corpus": "TAVERN",
            "source_revision": PINNED_TAVERN_REVISION,
            "reviewer_type": "HUMAN",
            "decisions": [
                {
                    "phrase_key": "Beethoven/B063:00:01",
                    "decision": "PRESERVE_VARIANTS",
                    "annotator_A_raw_sha256": hashlib.sha256(encoder_a).hexdigest(),
                    "annotator_B_raw_sha256": hashlib.sha256(encoder_b).hexdigest(),
                }
            ],
        }
        decision_sha = hashlib.sha256(
            json.dumps(decision, sort_keys=True).encode("utf-8")
        ).hexdigest()
        result = build_tavern_event_alignment_audit(
            decision,
            decision_artifact_sha256=decision_sha,
            archive_path=archive,
            expected_decision_sha256=decision_sha,
            expected_archive_sha256=archive_sha,
            expected_record_count=1,
            expected_selected_target_count=2,
            expected_alignment_manifest_sha256=None,
        )
        self.assertEqual(result["variant_event_alignment_candidate_count"], 0)
        self.assertEqual(result["quarantine_record_count"], 1)

    def test_summary_stays_non_authoritative_and_canonical(self):
        result = self._build()
        summary = build_tavern_event_alignment_summary(result)
        self.assertEqual(summary["schema_version"], SUMMARY_SCHEMA)
        self.assertNotIn("records", summary)
        self.assertFalse(summary["training_authorized"])
        self.assertTrue(canonical_tavern_event_alignment_json(summary).endswith("\n"))


if __name__ == "__main__":
    unittest.main()
