from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from st_harmonic_training.receipts import (
    ReceiptError,
    build_receipt,
    canonical_receipt_json,
    hash_artifact,
    manifest_hash_fields,
)


class ArtifactReceiptTests(unittest.TestCase):
    def make_file(self, root: Path, name: str, data: bytes) -> Path:
        path = root / name
        path.write_bytes(data)
        return path

    def test_hash_matches_independent_sha256(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = b"harmonic-evidence\x00v1\n"
            path = self.make_file(root, "analysis.tsv", data)
            evidence = hash_artifact("analysis", path)
            self.assertEqual(evidence.sha256, hashlib.sha256(data).hexdigest())
            self.assertEqual(evidence.size_bytes, len(data))

    def test_receipt_is_deterministic_and_role_ordered(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = self.make_file(root, "source.zip", b"raw")
            analysis = self.make_file(root, "analysis.tsv", b"analysis")
            first = build_receipt(
                "Corpus",
                "revision-1",
                {"analysis": analysis, "raw_archive": raw},
            )
            second = build_receipt(
                "Corpus",
                "revision-1",
                {"raw_archive": raw, "analysis": analysis},
            )
            self.assertEqual(canonical_receipt_json(first), canonical_receipt_json(second))
            self.assertEqual(
                [item["role"] for item in first["artifacts"]],
                ["raw_archive", "analysis"],
            )

    def test_partial_receipt_does_not_invent_missing_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            analysis = self.make_file(root, "analysis.tsv", b"analysis")
            receipt = build_receipt("Corpus", "revision-1", {"analysis": analysis})
            fields = manifest_hash_fields(receipt)
            self.assertIsNone(fields["raw_archive_sha256"])
            self.assertIsNone(fields["score_sha256"])
            self.assertIsNotNone(fields["analysis_sha256"])

    def test_same_file_cannot_satisfy_multiple_roles(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = self.make_file(root, "one.bin", b"same")
            with self.assertRaises(ReceiptError):
                build_receipt("Corpus", "revision-1", {"score": path, "analysis": path})

    def test_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ReceiptError):
                hash_artifact("analysis", Path(temp))

    def test_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = self.make_file(root, "target.tsv", b"target")
            link = root / "link.tsv"
            try:
                link.symlink_to(target)
            except OSError:
                self.skipTest("symlink creation is unavailable")
            with self.assertRaises(ReceiptError):
                hash_artifact("analysis", link)

    def test_unknown_role_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = self.make_file(root, "artifact.bin", b"x")
            with self.assertRaises(ReceiptError):
                hash_artifact("checkpoint", path)

    def test_tampered_digest_is_rejected(self) -> None:
        receipt = {
            "schema_version": "artifact-receipt-v1",
            "source_corpus": "Corpus",
            "immutable_revision": "revision-1",
            "artifacts": [
                {
                    "role": "analysis",
                    "filename": "analysis.tsv",
                    "size_bytes": 1,
                    "sha256": "not-a-digest",
                }
            ],
        }
        with self.assertRaises(ReceiptError):
            manifest_hash_fields(receipt)


if __name__ == "__main__":
    unittest.main()
