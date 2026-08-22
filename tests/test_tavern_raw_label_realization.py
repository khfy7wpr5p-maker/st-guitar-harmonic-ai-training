from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from st_harmonic_training.tavern_raw_label_realization import (
    TavernRawLabelRealizationError,
    build_tavern_raw_label_realization,
    build_tavern_raw_label_realization_summary,
    canonical_tavern_raw_label_realization_json,
)
from st_harmonic_training.tavern_structure import PINNED_TAVERN_REVISION


class TavernRawLabelRealizationTests(unittest.TestCase):
    def _decision(self, raw_hash: str) -> dict[str, object]:
        return {
            "schema_version": "st-tavern-human-adjudication-v1",
            "source_corpus": "TAVERN",
            "source_revision": PINNED_TAVERN_REVISION,
            "reviewer_type": "HUMAN",
            "decisions": [
                {
                    "phrase_key": "Beethoven/B063:00:01",
                    "decision": "SELECT_B",
                    "annotator_A_raw_sha256": "1" * 64,
                    "annotator_B_raw_sha256": raw_hash,
                }
            ],
        }

    def _archive(self, root: Path, raw: bytes, *, unsafe: bool = False) -> Path:
        path = root / "tavern.zip"
        member = (
            "../escape.krn"
            if unsafe
            else "TAVERN-master/Beethoven/B063/Encodings/Encoder_B/"
            "B063_00_01_encoderB.krn"
        )
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(member, raw)
        return path

    def test_selected_label_is_reread_and_hash_verified(self) -> None:
        raw = b"**chords\t**function\n*C:\t*C:\n4I\t4T\n*-\t*-\n"
        raw_hash = hashlib.sha256(raw).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            archive = self._archive(Path(tmp), raw)
            archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
            result = build_tavern_raw_label_realization(
                self._decision(raw_hash),
                decision_artifact_sha256="a" * 64,
                archive_path=archive,
                expected_decision_sha256="a" * 64,
                expected_archive_sha256=archive_hash,
                expected_count=1,
            )
        self.assertTrue(result["raw_label_realization_complete"])
        self.assertEqual(result["selected_label_count"], 1)
        self.assertEqual(result["selected_source_counts"], {"B": 1})
        self.assertFalse(result["normalization_complete"])
        self.assertFalse(result["training_authorized"])
        summary = build_tavern_raw_label_realization_summary(result)
        self.assertEqual(summary["record_count"], 1)

    def test_selected_hash_mismatch_fails_closed(self) -> None:
        raw = b"**chords\t**function\n4I\t4T\n*-\t*-\n"
        with tempfile.TemporaryDirectory() as tmp:
            archive = self._archive(Path(tmp), raw)
            archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
            with self.assertRaises(TavernRawLabelRealizationError):
                build_tavern_raw_label_realization(
                    self._decision("2" * 64),
                    decision_artifact_sha256="a" * 64,
                    archive_path=archive,
                    expected_decision_sha256="a" * 64,
                    expected_archive_sha256=archive_hash,
                    expected_count=1,
                )

    def test_archive_digest_mismatch_fails_closed(self) -> None:
        raw = b"**chords\t**function\n4I\t4T\n*-\t*-\n"
        raw_hash = hashlib.sha256(raw).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            archive = self._archive(Path(tmp), raw)
            with self.assertRaises(TavernRawLabelRealizationError):
                build_tavern_raw_label_realization(
                    self._decision(raw_hash),
                    decision_artifact_sha256="a" * 64,
                    archive_path=archive,
                    expected_decision_sha256="a" * 64,
                    expected_archive_sha256="b" * 64,
                    expected_count=1,
                )

    def test_unsafe_archive_member_fails_closed(self) -> None:
        raw = b"x"
        raw_hash = hashlib.sha256(raw).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            archive = self._archive(Path(tmp), raw, unsafe=True)
            archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
            with self.assertRaises(TavernRawLabelRealizationError):
                build_tavern_raw_label_realization(
                    self._decision(raw_hash),
                    decision_artifact_sha256="a" * 64,
                    archive_path=archive,
                    expected_decision_sha256="a" * 64,
                    expected_archive_sha256=archive_hash,
                    expected_count=1,
                )

    def test_ai_or_nonhuman_reviewer_fails_closed(self) -> None:
        raw = b"**chords\t**function\n4I\t4T\n*-\t*-\n"
        raw_hash = hashlib.sha256(raw).hexdigest()
        decision = self._decision(raw_hash)
        decision["reviewer_type"] = "AI"
        with tempfile.TemporaryDirectory() as tmp:
            archive = self._archive(Path(tmp), raw)
            archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
            with self.assertRaises(TavernRawLabelRealizationError):
                build_tavern_raw_label_realization(
                    decision,
                    decision_artifact_sha256="a" * 64,
                    archive_path=archive,
                    expected_decision_sha256="a" * 64,
                    expected_archive_sha256=archive_hash,
                    expected_count=1,
                )

    def test_output_is_deterministic(self) -> None:
        raw = b"**chords\t**function\n*C:\t*C:\n4I\t4T\n*-\t*-\n"
        raw_hash = hashlib.sha256(raw).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            archive = self._archive(Path(tmp), raw)
            archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
            kwargs = dict(
                decision_artifact_sha256="a" * 64,
                archive_path=archive,
                expected_decision_sha256="a" * 64,
                expected_archive_sha256=archive_hash,
                expected_count=1,
            )
            left = build_tavern_raw_label_realization(self._decision(raw_hash), **kwargs)
            right = build_tavern_raw_label_realization(self._decision(raw_hash), **kwargs)
        self.assertEqual(
            canonical_tavern_raw_label_realization_json(left),
            canonical_tavern_raw_label_realization_json(right),
        )


if __name__ == "__main__":
    unittest.main()
