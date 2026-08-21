from __future__ import annotations

import json
from pathlib import Path
import stat
import tempfile
import unittest
import zipfile

from st_harmonic_training.safe_ingest import (
    IngestSecurityError,
    ZipLimits,
    inspect_zip,
    load_bounded_json,
    parse_bounded_xml,
    safe_extract_zip,
    validate_unique_ids,
)


class SafeIngestTests(unittest.TestCase):
    def tempdir(self) -> Path:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        return Path(temp.name)

    def test_safe_zip_extracts_inside_destination(self) -> None:
        root = self.tempdir()
        archive = root / "safe.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("scores/piece.tsv", "ok\n")
        destination = root / "out"
        extracted = safe_extract_zip(archive, destination)
        self.assertEqual(len(extracted), 1)
        self.assertTrue(extracted[0].is_relative_to(destination.resolve()))
        self.assertEqual(extracted[0].read_text(encoding="utf-8"), "ok\n")

    def test_zip_path_traversal_is_rejected(self) -> None:
        root = self.tempdir()
        archive = root / "bad.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("../escape.txt", "no")
        with self.assertRaises(IngestSecurityError):
            inspect_zip(archive)

    def test_windows_style_zip_traversal_is_rejected(self) -> None:
        root = self.tempdir()
        archive = root / "bad-windows.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("..\\escape.txt", "no")
        with self.assertRaises(IngestSecurityError):
            inspect_zip(archive)

    def test_zip_symlink_is_rejected(self) -> None:
        root = self.tempdir()
        archive = root / "symlink.zip"
        info = zipfile.ZipInfo("link")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr(info, "target")
        with self.assertRaises(IngestSecurityError):
            inspect_zip(archive)

    def test_zip_high_compression_ratio_is_rejected(self) -> None:
        root = self.tempdir()
        archive = root / "ratio.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("huge.txt", "A" * 100_000)
        with self.assertRaises(IngestSecurityError):
            inspect_zip(archive, limits=ZipLimits(max_compression_ratio=2.0))

    def test_zip_script_member_is_rejected(self) -> None:
        root = self.tempdir()
        archive = root / "script.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("run.sh", "echo unsafe")
        with self.assertRaises(IngestSecurityError):
            inspect_zip(archive)

    def test_xml_dtd_entity_is_rejected(self) -> None:
        root = self.tempdir()
        path = root / "bad.xml"
        path.write_text('<!DOCTYPE x [<!ENTITY y "boom">]><x>&y;</x>', encoding="utf-8")
        with self.assertRaises(IngestSecurityError):
            parse_bounded_xml(path)

    def test_invalid_utf8_json_is_rejected(self) -> None:
        root = self.tempdir()
        path = root / "bad.json"
        path.write_bytes(b"{\xff}")
        with self.assertRaises(IngestSecurityError):
            load_bounded_json(path)

    def test_duplicate_json_keys_are_rejected(self) -> None:
        root = self.tempdir()
        path = root / "duplicate.json"
        path.write_text('{"id": 1, "id": 2}', encoding="utf-8")
        with self.assertRaises(IngestSecurityError):
            load_bounded_json(path)

    def test_duplicate_record_ids_are_rejected(self) -> None:
        records = [{"id": "same"}, {"id": "same"}]
        with self.assertRaises(IngestSecurityError):
            validate_unique_ids(records)

    def test_oversized_json_is_rejected(self) -> None:
        root = self.tempdir()
        path = root / "big.json"
        path.write_text(json.dumps({"x": "A" * 100}), encoding="utf-8")
        with self.assertRaises(IngestSecurityError):
            load_bounded_json(path, max_bytes=20)


if __name__ == "__main__":
    unittest.main()
