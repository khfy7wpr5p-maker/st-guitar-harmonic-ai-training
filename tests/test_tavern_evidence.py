from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import zipfile

from st_harmonic_training.safe_ingest import IngestSecurityError
from st_harmonic_training.tavern_evidence import (
    TavernEvidenceError,
    build_tavern_evidence,
    canonical_evidence_json,
)


BASE_MEMBERS = {
    "README.md": b"# TAVERN\n",
    "LICENSE": b"CC BY-SA 4.0\n",
    "Beethoven/B063/Krn/B063_00_01_score.krn": b"score-a\n",
    "Beethoven/B063/Encodings/Encoder_A/B063_00_01_encoderA.krn": b"analysis-a\n",
    "Beethoven/B063/Encodings/Encoder_B/B063_00_01_encoderB.krn": b"analysis-b\n",
    "Beethoven/B063/Joined/B063_00_01a_a.krn": b"joined-a\n",
    "Mozart/K025/Krn/K025_00_01_score.krn": b"score-m\n",
    "Mozart/K025/Encodings/Encoder_A/K025_00_01_encoderA.krn": b"analysis-m\n",
}


class TavernEvidenceTests(unittest.TestCase):
    def write_zip(
        self,
        path: Path,
        *,
        root: str = "TAVERN-master",
        members: dict[str, bytes] | None = None,
        reverse: bool = False,
    ) -> None:
        values = list((members or BASE_MEMBERS).items())
        if reverse:
            values.reverse()
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name, data in values:
                zf.writestr(f"{root}/{name}", data)

    def build(self, path: Path) -> dict[str, object]:
        return build_tavern_evidence(
            path,
            immutable_revision="7cc65dc5365603a92376af50ac71491bea7a16ae",
        )

    def test_inventory_digests_ignore_archive_root_and_member_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = root / "first.zip"
            second = root / "second.zip"
            self.write_zip(first, root="TAVERN-master")
            self.write_zip(second, root="TAVERN-7cc65dc", reverse=True)
            a = self.build(first)
            b = self.build(second)
            self.assertNotEqual(a["raw_archive"]["sha256"], b["raw_archive"]["sha256"])
            self.assertEqual(
                a["manifest_hash_fields"]["score_sha256"],
                b["manifest_hash_fields"]["score_sha256"],
            )
            self.assertEqual(
                a["manifest_hash_fields"]["analysis_sha256"],
                b["manifest_hash_fields"]["analysis_sha256"],
            )

    def test_score_tamper_changes_only_score_inventory_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = root / "first.zip"
            second = root / "second.zip"
            self.write_zip(first)
            changed = dict(BASE_MEMBERS)
            changed["Beethoven/B063/Krn/B063_00_01_score.krn"] = b"tampered-score\n"
            self.write_zip(second, members=changed)
            a = self.build(first)
            b = self.build(second)
            self.assertNotEqual(
                a["manifest_hash_fields"]["score_sha256"],
                b["manifest_hash_fields"]["score_sha256"],
            )
            self.assertEqual(
                a["manifest_hash_fields"]["analysis_sha256"],
                b["manifest_hash_fields"]["analysis_sha256"],
            )

    def test_joined_files_do_not_change_analysis_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = root / "first.zip"
            second = root / "second.zip"
            self.write_zip(first)
            changed = dict(BASE_MEMBERS)
            changed["Beethoven/B063/Joined/B063_00_01a_a.krn"] = b"changed-joined\n"
            self.write_zip(second, members=changed)
            a = self.build(first)
            b = self.build(second)
            self.assertEqual(
                a["manifest_hash_fields"]["analysis_sha256"],
                b["manifest_hash_fields"]["analysis_sha256"],
            )
            self.assertNotEqual(
                a["derived_validation_evidence"]["joined_inventory_sha256"],
                b["derived_validation_evidence"]["joined_inventory_sha256"],
            )

    def test_backup_members_are_excluded_and_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "source.zip"
            members = dict(BASE_MEMBERS)
            members["Beethoven/B063/Encodings/Encoder_B/old.krn~"] = b"backup\n"
            self.write_zip(path, members=members)
            evidence = self.build(path)
            self.assertIn(
                "Beethoven/B063/Encodings/Encoder_B/old.krn~",
                evidence["excluded_members"],
            )
            self.assertEqual(evidence["inventory_counts"]["analysis"], 3)

    def test_missing_required_metadata_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "source.zip"
            members = dict(BASE_MEMBERS)
            del members["LICENSE"]
            self.write_zip(path, members=members)
            with self.assertRaises(TavernEvidenceError):
                self.build(path)

    def test_multiple_archive_roots_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "source.zip"
            self.write_zip(path)
            with zipfile.ZipFile(path, "a", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("other-root/file.txt", b"x")
            with self.assertRaises(TavernEvidenceError):
                self.build(path)

    def test_unsafe_zip_path_is_rejected_by_ingest_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "source.zip"
            self.write_zip(path)
            with zipfile.ZipFile(path, "a", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("TAVERN-master/../escape.txt", b"x")
            with self.assertRaises(IngestSecurityError):
                self.build(path)

    def test_canonical_evidence_json_is_stable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "source.zip"
            self.write_zip(path)
            evidence = self.build(path)
            self.assertEqual(
                canonical_evidence_json(evidence),
                canonical_evidence_json(dict(reversed(list(evidence.items())))),
            )


if __name__ == "__main__":
    unittest.main()
