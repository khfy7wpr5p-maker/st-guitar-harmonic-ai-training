from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile

from st_harmonic_training.tavern_kern_features import (
    ADAPTER_VERSION,
    TavernKernFeatureError,
    build_tavern_kern_features,
    canonical_tavern_kern_feature_json,
    extract_kern_bow_features,
)
from st_harmonic_training.tavern_score_input_realization import SCORE_INPUT_SCHEMA
from st_harmonic_training.tavern_structure import PINNED_TAVERN_REVISION


SCORE = (
    "**kern\t**kern\n"
    "*staff2\t*staff1\n"
    "*C:\t*C:\n"
    "4C 4E 4G\t2c\n"
    ".\t4d\n"
    "=2\t=2\n"
    "*-\t*-\n"
).encode("utf-8")


class KernFeatureParserTests(unittest.TestCase):
    def test_surface_tokens_are_counted_without_musical_rewrite(self):
        features, stats = extract_kern_bow_features(SCORE.decode("utf-8"))
        self.assertEqual(features["SPINE_COUNT::2"], 1)
        self.assertEqual(features["KERN_ATOM::4C"], 1)
        self.assertEqual(features["KERN_ATOM::4E"], 1)
        self.assertEqual(features["KERN_ATOM::4G"], 1)
        self.assertEqual(features["KERN_ATOM::2c"], 1)
        self.assertEqual(features["NULL"], 1)
        self.assertEqual(features["BARLINE"], 2)
        self.assertEqual(features["INTERP::*C:"], 2)
        self.assertEqual(stats["kern_spine_count"], 2)

    def test_multiple_exclusive_headers_fail_closed(self):
        raw = "**kern\n4c\n**kern\n4d\n*-\n"
        with self.assertRaises(TavernKernFeatureError):
            extract_kern_bow_features(raw)

    def test_no_kern_data_atoms_fail_closed(self):
        raw = "**kern\n*C:\n.\n*-\n"
        with self.assertRaises(TavernKernFeatureError):
            extract_kern_bow_features(raw)


class KernFeatureBuilderTests(unittest.TestCase):
    def setup_payload(self, root: Path):
        archive = root / "tavern.zip"
        member = "TAVERN-test/Beethoven/B063/Krn/B063_00_01_score.krn"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr(member, SCORE)
        archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
        score_sha = hashlib.sha256(SCORE).hexdigest()
        score_input_manifest = "c" * 64
        realization = {
            "schema_version": SCORE_INPUT_SCHEMA,
            "source_corpus": "TAVERN_REVIEWED_694",
            "source_revision": PINNED_TAVERN_REVISION,
            "archive_sha256": archive_sha,
            "score_input_manifest_sha256": score_input_manifest,
            "record_count": 1,
            "score_input_realization_complete": True,
            "deterministic_feature_schema_complete": False,
            "training_authorized": False,
            "records": [
                {
                    "phrase_key": "Beethoven/B063:00:01",
                    "score_member": "Beethoven/B063/Krn/B063_00_01_score.krn",
                    "score_sha256": score_sha,
                    "byte_count": len(SCORE),
                }
            ],
        }
        return archive, archive_sha, score_input_manifest, realization

    def test_builder_is_label_blind_and_keeps_training_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive, archive_sha, score_manifest, realization = self.setup_payload(Path(tmp))
            result = build_tavern_kern_features(
                realization,
                archive_path=archive,
                expected_record_count=1,
                expected_score_input_manifest_sha256=score_manifest,
                expected_archive_sha256=archive_sha,
            )
            self.assertEqual(result["adapter_version"], ADAPTER_VERSION)
            self.assertEqual(result["record_count"], 1)
            self.assertEqual(result["kern_spine_counts"], {"2": 1})
            self.assertTrue(result["deterministic_feature_schema_complete"])
            self.assertFalse(result["training_payload_manifest_complete"])
            self.assertFalse(result["training_authorized"])

    def test_score_hash_tamper_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive, archive_sha, score_manifest, realization = self.setup_payload(Path(tmp))
            realization["records"][0]["score_sha256"] = "0" * 64
            with self.assertRaises(TavernKernFeatureError):
                build_tavern_kern_features(
                    realization,
                    archive_path=archive,
                    expected_record_count=1,
                    expected_score_input_manifest_sha256=score_manifest,
                    expected_archive_sha256=archive_sha,
                )

    def test_upstream_training_authority_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive, archive_sha, score_manifest, realization = self.setup_payload(Path(tmp))
            realization["training_authorized"] = True
            with self.assertRaises(TavernKernFeatureError):
                build_tavern_kern_features(
                    realization,
                    archive_path=archive,
                    expected_record_count=1,
                    expected_score_input_manifest_sha256=score_manifest,
                    expected_archive_sha256=archive_sha,
                )

    def test_output_is_deterministic_for_same_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive, archive_sha, score_manifest, realization = self.setup_payload(Path(tmp))
            left = build_tavern_kern_features(
                realization,
                archive_path=archive,
                expected_record_count=1,
                expected_score_input_manifest_sha256=score_manifest,
                expected_archive_sha256=archive_sha,
            )
            right = build_tavern_kern_features(
                realization,
                archive_path=archive,
                expected_record_count=1,
                expected_score_input_manifest_sha256=score_manifest,
                expected_archive_sha256=archive_sha,
            )
            self.assertEqual(
                canonical_tavern_kern_feature_json(left),
                canonical_tavern_kern_feature_json(right),
            )


if __name__ == "__main__":
    unittest.main()
