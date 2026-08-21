from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import zipfile

from st_harmonic_training.safe_ingest import IngestSecurityError
from st_harmonic_training.tavern_structure import (
    PINNED_TAVERN_REVISION,
    TavernStructureError,
    build_tavern_structure_audit,
    canonical_structure_json,
)


BASE_MEMBERS = {
    "README.md": b"# TAVERN\n",
    "LICENSE": b"CC BY-SA 4.0\n",
    "Beethoven/B063/Krn/B063_00_01_score.krn": b"score\n",
    "Beethoven/B063/Encodings/Encoder_A/B063_00_01_encoderA.krn": b"a\n",
    "Beethoven/B063/Encodings/Encoder_B/B063_00_01_encoderB.krn": b"b\n",
    "Beethoven/B063/Joined/B063_00_01a_a.krn": b"joined-a\n",
    "Beethoven/B063/Joined/B063_00_01a_b.krn": b"joined-b\n",
}


class TavernStructureTests(unittest.TestCase):
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
        return build_tavern_structure_audit(
            path,
            immutable_revision=PINNED_TAVERN_REVISION,
        )

    def test_documented_ab_pair_is_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "tavern.zip"
            self.write_zip(archive)
            audit = self.build(archive)
        self.assertEqual(audit["phrase_status_counts"]["PAIR_COMPLETE"], 1)
        self.assertEqual(audit["observed_counts"]["joined_AB_phrase_keys"], 1)
        self.assertFalse(audit["training_authorized"])

    def test_undocumented_encoder_c_is_quarantined(self) -> None:
        members = dict(BASE_MEMBERS)
        members[
            "Beethoven/B063/Encodings/Encoder_C/B063_00_01_encoderC.krn"
        ] = b"c\n"
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "tavern.zip"
            self.write_zip(archive, members=members)
            audit = self.build(archive)
        self.assertEqual(audit["undocumented_primary_annotators"], {"C": 1})
        self.assertIn("UNDOCUMENTED_PRIMARY_ANNOTATOR:C:1", audit["blockers"])

    def test_v_prefix_score_and_contentless_joined_share_phrase_key(self) -> None:
        members = {
            "README.md": b"# TAVERN\n",
            "LICENSE": b"license\n",
            "Beethoven/B071/Krn/Wo071_V00_01_score.krn": b"score\n",
            "Beethoven/B071/Encodings/Encoder_B/B071_00_01_encoderB.krn": b"b\n",
            "Beethoven/B071/Joined/B071_00_01_a.krn": b"joined-a\n",
            "Beethoven/B071/Joined/B071_00_01_b.krn": b"joined-b\n",
        }
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "tavern.zip"
            self.write_zip(archive, members=members)
            audit = self.build(archive)
        self.assertEqual(audit["observed_counts"]["phrase_keys"], 1)
        self.assertEqual(audit["phrase_status_counts"]["SCORE_B_ONLY"], 1)
        self.assertEqual(audit["observed_counts"]["joined_AB_phrase_keys"], 1)

    def test_whole_work_krn_is_support_not_phrase(self) -> None:
        members = dict(BASE_MEMBERS)
        members["Beethoven/B063/Krn/Wo063.krn"] = b"whole work\n"
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "tavern.zip"
            self.write_zip(archive, members=members)
            audit = self.build(archive)
        self.assertEqual(audit["observed_counts"]["phrase_keys"], 1)
        self.assertEqual(audit["observed_counts"]["support_score_krn_files"], 1)

    def test_duplicate_phrase_role_fails_closed(self) -> None:
        members = dict(BASE_MEMBERS)
        members["Beethoven/B063/Krn/alternate_00_01_score.krn"] = b"duplicate\n"
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "tavern.zip"
            self.write_zip(archive, members=members)
            with self.assertRaises(TavernStructureError):
                self.build(archive)

    def test_encoder_directory_filename_mismatch_fails_closed(self) -> None:
        members = dict(BASE_MEMBERS)
        del members["Beethoven/B063/Encodings/Encoder_A/B063_00_01_encoderA.krn"]
        members[
            "Beethoven/B063/Encodings/Encoder_A/B063_00_01_encoderB.krn"
        ] = b"mismatch\n"
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "tavern.zip"
            self.write_zip(archive, members=members)
            with self.assertRaises(TavernStructureError):
                self.build(archive)

    def test_unreviewed_revision_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "tavern.zip"
            self.write_zip(archive)
            with self.assertRaises(TavernStructureError):
                build_tavern_structure_audit(
                    archive,
                    immutable_revision="0" * 40,
                )

    def test_root_name_and_zip_order_do_not_change_structure_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            left = Path(tmp) / "left.zip"
            right = Path(tmp) / "right.zip"
            self.write_zip(left, root="TAVERN-master")
            self.write_zip(right, root="TAVERN-commit", reverse=True)
            left_payload = canonical_structure_json(self.build(left))
            right_payload = canonical_structure_json(self.build(right))
        self.assertEqual(left_payload, right_payload)

    def test_unsafe_zip_member_is_rejected_before_structure_parse(self) -> None:
        members = dict(BASE_MEMBERS)
        members["evil.py"] = b"print('no')\n"
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "tavern.zip"
            self.write_zip(archive, members=members)
            with self.assertRaises(IngestSecurityError):
                self.build(archive)


if __name__ == "__main__":
    unittest.main()
