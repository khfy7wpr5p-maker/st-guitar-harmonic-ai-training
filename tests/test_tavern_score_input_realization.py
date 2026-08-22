from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile

from st_harmonic_training.tavern_raw_label_realization import _validated_zip_members
from st_harmonic_training.tavern_score_input_realization import (
    TavernScoreInputRealizationError,
    _archive_root,
    _score_inventory_digest,
    build_tavern_score_input_realization,
    canonical_tavern_score_input_json,
)
from st_harmonic_training.tavern_structure import PINNED_TAVERN_REVISION


class TavernScoreInputRealizationTests(unittest.TestCase):
    def archive(self, root: Path, *, score_name: str = "B063_00_01_score.krn", score_body: bytes | None = None):
        if score_body is None:
            score_body = b"**kern\t**kern\n*staff2\t*staff1\n*C:\t*C:\n4C\t4c\n*-\t*-\n"
        path = root / "tavern.zip"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("TAVERN-test/README.md", "test")
            zf.writestr("TAVERN-test/LICENSE", "test")
            zf.writestr(f"TAVERN-test/Beethoven/B063/Krn/{score_name}", score_body)
        with zipfile.ZipFile(path) as zf:
            infos = _validated_zip_members(zf)
            archive_root = _archive_root(infos)
            inventory_sha, inventory_count = _score_inventory_digest(
                zf, infos, root=archive_root
            )
        return path, hashlib.sha256(path.read_bytes()).hexdigest(), inventory_sha, inventory_count

    def decisions(self):
        return {
            "schema_version": "st-tavern-human-adjudication-v1",
            "source_corpus": "TAVERN",
            "source_revision": PINNED_TAVERN_REVISION,
            "reviewer_type": "HUMAN",
            "decisions": [
                {
                    "phrase_key": "Beethoven/B063:00:01",
                    "decision": "SELECT_B",
                }
            ],
        }

    def build(self, *, score_name: str = "B063_00_01_score.krn", score_body: bytes | None = None, mutate=None):
        with tempfile.TemporaryDirectory() as tmp:
            archive, archive_sha, inventory_sha, _ = self.archive(
                Path(tmp), score_name=score_name, score_body=score_body
            )
            decisions = self.decisions()
            if mutate is not None:
                mutate(decisions)
            return build_tavern_score_input_realization(
                decisions,
                decision_artifact_sha256="a" * 64,
                archive_path=archive,
                expected_decision_sha256="a" * 64,
                expected_archive_sha256=archive_sha,
                expected_score_inventory_sha256=inventory_sha,
                expected_count=1,
            )

    def test_realizes_one_hash_bound_utf8_kern_score(self):
        result = self.build()
        self.assertEqual(result["record_count"], 1)
        self.assertEqual(result["score_input_count"], 1)
        self.assertEqual(result["score_inventory_member_count"], 1)
        self.assertTrue(result["score_input_realization_complete"])
        self.assertFalse(result["deterministic_feature_schema_complete"])
        self.assertFalse(result["training_authorized"])
        self.assertEqual(result["records"][0]["phrase_key"], "Beethoven/B063:00:01")

    def test_optional_v_filename_is_supported(self):
        result = self.build(score_name="B063_V00_01_score.krn")
        self.assertTrue(result["score_input_realization_complete"])

    def test_missing_score_fails_closed(self):
        with self.assertRaises(TavernScoreInputRealizationError):
            self.build(score_name="B063_00_02_score.krn")

    def test_non_utf8_score_fails_closed(self):
        with self.assertRaises(TavernScoreInputRealizationError):
            self.build(score_body=b"**kern\n\xff\n*-\n")

    def test_score_without_kern_header_fails_closed(self):
        with self.assertRaises(TavernScoreInputRealizationError):
            self.build(score_body=b"**text\nhello\n*-\n")

    def test_duplicate_phrase_key_fails_closed(self):
        def mutate(data):
            data["decisions"].append(dict(data["decisions"][0]))
        with tempfile.TemporaryDirectory() as tmp:
            archive, archive_sha, inventory_sha, _ = self.archive(Path(tmp))
            decisions = self.decisions()
            mutate(decisions)
            with self.assertRaises(TavernScoreInputRealizationError):
                build_tavern_score_input_realization(
                    decisions,
                    decision_artifact_sha256="a" * 64,
                    archive_path=archive,
                    expected_decision_sha256="a" * 64,
                    expected_archive_sha256=archive_sha,
                    expected_score_inventory_sha256=inventory_sha,
                    expected_count=2,
                )

    def test_output_is_deterministic(self):
        left = self.build()
        right = self.build()
        left["archive_sha256"] = "x"
        right["archive_sha256"] = "x"
        self.assertEqual(
            canonical_tavern_score_input_json(left),
            canonical_tavern_score_input_json(right),
        )


if __name__ == "__main__":
    unittest.main()
