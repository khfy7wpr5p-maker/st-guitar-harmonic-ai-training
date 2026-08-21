from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from st_harmonic_training.tavern_ab_compare import canonical_ab_comparison_json
from st_harmonic_training.tavern_review_package import (
    TavernReviewPackageError,
    write_tavern_review_package,
)
from st_harmonic_training.tavern_structure import PINNED_TAVERN_REVISION


class TavernReviewPackageTests(unittest.TestCase):
    def make_fixture(self, root: Path) -> tuple[Path, dict[str, object], str, str]:
        archive = root / "TAVERN-fixture.zip"
        members = {
            "TAVERN-fixture/README.md": b"fixture\n",
            "TAVERN-fixture/LICENSE": b"CC BY-SA 4.0\n",
            "TAVERN-fixture/Beethoven/B063/Encodings/Encoder_A/B063_00_01_encoderA.krn": b"same\n",
            "TAVERN-fixture/Beethoven/B063/Encodings/Encoder_B/B063_00_01_encoderB.krn": b"same\n",
            "TAVERN-fixture/Beethoven/B063/Encodings/Encoder_A/B063_00_02_encoderA.krn": b"<script>alert('x')</script>\nA\n",
            "TAVERN-fixture/Beethoven/B063/Encodings/Encoder_B/B063_00_02_encoderB.krn": b"B\n",
        }
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as zf:
            for name, payload in members.items():
                zf.writestr(name, payload)

        def sha(data: bytes) -> str:
            return hashlib.sha256(data).hexdigest()

        def canonical_sha(data: bytes) -> str:
            text = data.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
            return sha(text.encode("utf-8"))

        a1 = members["TAVERN-fixture/Beethoven/B063/Encodings/Encoder_A/B063_00_01_encoderA.krn"]
        b1 = members["TAVERN-fixture/Beethoven/B063/Encodings/Encoder_B/B063_00_01_encoderB.krn"]
        a2 = members["TAVERN-fixture/Beethoven/B063/Encodings/Encoder_A/B063_00_02_encoderA.krn"]
        b2 = members["TAVERN-fixture/Beethoven/B063/Encodings/Encoder_B/B063_00_02_encoderB.krn"]
        comparison: dict[str, object] = {
            "schema_version": "st-tavern-ab-comparison-v1",
            "source_corpus": "TAVERN",
            "source_revision": PINNED_TAVERN_REVISION,
            "raw_archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            "comparison_scope": "EVIDENCE_ONLY_NO_SEMANTIC_EQUIVALENCE",
            "pair_count": 2,
            "relation_counts": {"BYTE_EXACT": 1, "TEXT_DIFFERENT": 1},
            "comparisons": [
                {
                    "phrase_key": "Beethoven/B063:00:01",
                    "relation": "BYTE_EXACT",
                    "annotator_A_raw_sha256": sha(a1),
                    "annotator_B_raw_sha256": sha(b1),
                    "annotator_A_canonical_text_sha256": canonical_sha(a1),
                    "annotator_B_canonical_text_sha256": canonical_sha(b1),
                },
                {
                    "phrase_key": "Beethoven/B063:00:02",
                    "relation": "TEXT_DIFFERENT",
                    "annotator_A_raw_sha256": sha(a2),
                    "annotator_B_raw_sha256": sha(b2),
                    "annotator_A_canonical_text_sha256": canonical_sha(a2),
                    "annotator_B_canonical_text_sha256": canonical_sha(b2),
                },
            ],
            "adjudication_authorized": False,
            "gold_assignment_authorized": False,
            "partition_assignment_authorized": False,
            "training_authorized": False,
        }
        comparison_sha = hashlib.sha256(
            canonical_ab_comparison_json(comparison).encode("utf-8")
        ).hexdigest()
        raw_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
        return archive, comparison, raw_sha, comparison_sha

    def write_fixture_package(
        self,
        root: Path,
        *,
        output_name: str = "review",
        batch_size: int = 1,
    ) -> tuple[dict[str, object], Path]:
        archive, comparison, raw_sha, comparison_sha = self.make_fixture(root)
        output = root / output_name
        manifest = write_tavern_review_package(
            archive,
            comparison,
            output,
            batch_size=batch_size,
            expected_raw_archive_sha256=raw_sha,
            expected_comparison_sha256=comparison_sha,
            expected_pair_count=2,
        )
        return manifest, output

    def test_package_is_batched_and_never_preselects_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest, output = self.write_fixture_package(Path(tmp), batch_size=1)
            self.assertEqual(manifest["pair_count"], 2)
            self.assertEqual(manifest["batch_count"], 2)
            self.assertFalse(manifest["decisions_preselected"])
            self.assertFalse(manifest["gold_assignment_authorized"])
            self.assertFalse(manifest["partition_assignment_authorized"])
            self.assertFalse(manifest["training_authorized"])
            first = (output / "batch-001.html").read_text(encoding="utf-8")
            second = (output / "batch-002.html").read_text(encoding="utf-8")
            self.assertNotIn(" checked", first)
            self.assertNotIn(" checked", second)
            self.assertIn("CONFIRM_EQUIVALENT", first)
            self.assertNotIn('value="SELECT_A"', first)
            self.assertIn('value="SELECT_A"', second)
            self.assertNotIn('value="CONFIRM_EQUIVALENT"', second)

    def test_untrusted_annotation_text_is_html_escaped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, output = self.write_fixture_package(Path(tmp), batch_size=1)
            second = (output / "batch-002.html").read_text(encoding="utf-8")
            self.assertNotIn("<script>alert('x')</script>", second)
            self.assertIn("&lt;script&gt;alert('x')&lt;/script&gt;", second)
            self.assertIn("Content-Security-Policy", second)
            self.assertIn("connect-src 'none'", second)

    def test_export_payload_is_human_only_and_evidence_bound(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest, output = self.write_fixture_package(Path(tmp), batch_size=2)
            page = (output / "batch-001.html").read_text(encoding="utf-8")
            self.assertIn("reviewer_type: 'HUMAN'", page)
            self.assertIn(str(manifest["comparison_evidence_sha256"]), page)
            self.assertIn("No option is preselected", page)

    def test_manifest_contains_no_raw_annotation_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest, output = self.write_fixture_package(Path(tmp), batch_size=2)
            payload = (output / "manifest.json").read_text(encoding="utf-8")
            self.assertNotIn("alert('x')", payload)
            self.assertTrue(manifest["raw_annotation_text_in_ephemeral_package"])
            self.assertFalse(manifest["raw_annotation_text_committed"])

    def test_wrong_raw_archive_hash_fails_closed_and_cleans_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive, comparison, _, comparison_sha = self.make_fixture(root)
            output = root / "review"
            with self.assertRaises(TavernReviewPackageError):
                write_tavern_review_package(
                    archive,
                    comparison,
                    output,
                    expected_raw_archive_sha256="0" * 64,
                    expected_comparison_sha256=comparison_sha,
                    expected_pair_count=2,
                )
            self.assertFalse(output.exists())

    def test_wrong_comparison_hash_fails_closed_and_cleans_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive, comparison, raw_sha, _ = self.make_fixture(root)
            output = root / "review"
            with self.assertRaises(TavernReviewPackageError):
                write_tavern_review_package(
                    archive,
                    comparison,
                    output,
                    expected_raw_archive_sha256=raw_sha,
                    expected_comparison_sha256="0" * 64,
                    expected_pair_count=2,
                )
            self.assertFalse(output.exists())

    def test_annotation_hash_anchor_tamper_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive, comparison, raw_sha, _ = self.make_fixture(root)
            comparison["comparisons"][0]["annotator_A_raw_sha256"] = "f" * 64
            comparison_sha = hashlib.sha256(
                canonical_ab_comparison_json(comparison).encode("utf-8")
            ).hexdigest()
            output = root / "review"
            with self.assertRaises(TavernReviewPackageError):
                write_tavern_review_package(
                    archive,
                    comparison,
                    output,
                    expected_raw_archive_sha256=raw_sha,
                    expected_comparison_sha256=comparison_sha,
                    expected_pair_count=2,
                )
            self.assertFalse(output.exists())

    def test_nonempty_output_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive, comparison, raw_sha, comparison_sha = self.make_fixture(root)
            output = root / "review"
            output.mkdir()
            (output / "old.html").write_text("old", encoding="utf-8")
            with self.assertRaises(TavernReviewPackageError):
                write_tavern_review_package(
                    archive,
                    comparison,
                    output,
                    expected_raw_archive_sha256=raw_sha,
                    expected_comparison_sha256=comparison_sha,
                    expected_pair_count=2,
                )
            self.assertEqual((output / "old.html").read_text(encoding="utf-8"), "old")

    def test_same_inputs_produce_identical_package_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive, comparison, raw_sha, comparison_sha = self.make_fixture(root)
            left = root / "left"
            right = root / "right"
            for output in (left, right):
                write_tavern_review_package(
                    archive,
                    comparison,
                    output,
                    batch_size=1,
                    expected_raw_archive_sha256=raw_sha,
                    expected_comparison_sha256=comparison_sha,
                    expected_pair_count=2,
                )
            left_files = sorted(path.name for path in left.iterdir())
            right_files = sorted(path.name for path in right.iterdir())
            self.assertEqual(left_files, right_files)
            for name in left_files:
                self.assertEqual((left / name).read_bytes(), (right / name).read_bytes())

    def test_manifest_batch_hashes_match_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest, output = self.write_fixture_package(Path(tmp), batch_size=1)
            committed = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(committed["batch_count"], 2)
            for batch in committed["batches"]:
                observed = hashlib.sha256((output / batch["filename"]).read_bytes()).hexdigest()
                self.assertEqual(observed, batch["sha256"])
            index_sha = hashlib.sha256((output / "index.html").read_bytes()).hexdigest()
            self.assertEqual(index_sha, manifest["index_sha256"])


if __name__ == "__main__":
    unittest.main()
