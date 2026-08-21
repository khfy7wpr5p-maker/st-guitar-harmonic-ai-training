from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile

from st_harmonic_training.safe_ingest import IngestSecurityError
from st_harmonic_training.tavern_ab_compare import (
    TavernABComparisonError,
    build_tavern_ab_comparison,
    canonical_ab_comparison_json,
)
from st_harmonic_training.tavern_structure import PINNED_TAVERN_REVISION


class TavernABComparisonTests(unittest.TestCase):
    def phrase_gate(self, count: int = 1) -> dict[str, object]:
        return {
            "schema_version": "st-tavern-phrase-gate-v1",
            "source_corpus": "TAVERN",
            "source_revision": PINNED_TAVERN_REVISION,
            "teacher_gold_candidate_count": count,
            "queues": {
                "human_pair_adjudication": {
                    "count": count,
                    "decision": "A_B_CONTENT_COMPARISON_REQUIRED",
                    "gold_tier_assigned": None,
                }
            },
            "gold_assignment_authorized": False,
            "partition_assignment_authorized": False,
            "training_authorized": False,
        }

    def write_zip(
        self,
        path: Path,
        *,
        a: bytes = b"**harm\n*C:\nI\n*-\n",
        b: bytes = b"**harm\n*C:\nI\n*-\n",
        include_c: bool = False,
        b_directory: str = "Encoder_B",
        duplicate_a: bool = False,
    ) -> str:
        root = "TAVERN-fixture"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"{root}/README.md", "fixture")
            zf.writestr(f"{root}/LICENSE", "fixture")
            zf.writestr(
                f"{root}/Beethoven/B063/Krn/B063_00_01_score.krn",
                "**kern\n*-\n",
            )
            a_name = f"{root}/Beethoven/B063/Encodings/Encoder_A/B063_00_01_encoderA.krn"
            zf.writestr(a_name, a)
            if duplicate_a:
                zf.writestr(a_name, a)
            zf.writestr(
                f"{root}/Beethoven/B063/Encodings/{b_directory}/B063_00_01_encoderB.krn",
                b,
            )
            if include_c:
                zf.writestr(
                    f"{root}/Beethoven/B063/Encodings/Encoder_C/B063_00_01_encoderC.krn",
                    b"**harm\nV\n*-\n",
                )
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def compare(self, archive: Path, gate: dict[str, object] | None = None) -> dict[str, object]:
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        return build_tavern_ab_comparison(
            archive,
            gate or self.phrase_gate(),
            expected_raw_archive_sha256=digest,
        )

    def test_byte_exact_pair_is_evidence_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "fixture.zip"
            self.write_zip(archive)
            evidence = self.compare(archive)
        self.assertEqual(evidence["pair_count"], 1)
        self.assertEqual(evidence["relation_counts"], {"BYTE_EXACT": 1})
        self.assertFalse(evidence["adjudication_authorized"])
        self.assertFalse(evidence["gold_assignment_authorized"])
        self.assertFalse(evidence["partition_assignment_authorized"])
        self.assertFalse(evidence["training_authorized"])

    def test_line_ending_only_difference_is_not_semantic_gold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "fixture.zip"
            self.write_zip(
                archive,
                a=b"**harm\r\n*C:\r\nI\r\n*-\r\n",
                b=b"**harm\n*C:\nI\n*-\n",
            )
            evidence = self.compare(archive)
        self.assertEqual(
            evidence["relation_counts"],
            {"TEXT_LINE_ENDING_EQUIVALENT": 1},
        )
        self.assertFalse(evidence["gold_assignment_authorized"])

    def test_different_text_is_reported_without_content_leakage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "fixture.zip"
            self.write_zip(archive, a=b"I\n", b=b"V\n")
            evidence = self.compare(archive)
        self.assertEqual(evidence["relation_counts"], {"TEXT_DIFFERENT": 1})
        record = evidence["comparisons"][0]
        self.assertEqual(
            set(record),
            {
                "phrase_key",
                "relation",
                "annotator_A_raw_sha256",
                "annotator_B_raw_sha256",
                "annotator_A_canonical_text_sha256",
                "annotator_B_canonical_text_sha256",
            },
        )

    def test_invalid_utf8_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "fixture.zip"
            self.write_zip(archive, a=b"\xff\xfe", b=b"I\n")
            with self.assertRaises(TavernABComparisonError):
                self.compare(archive)

    def test_pair_count_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "fixture.zip"
            self.write_zip(archive)
            with self.assertRaises(TavernABComparisonError):
                self.compare(archive, self.phrase_gate(count=2))

    def test_wrong_raw_archive_hash_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "fixture.zip"
            self.write_zip(archive)
            with self.assertRaises(TavernABComparisonError):
                build_tavern_ab_comparison(
                    archive,
                    self.phrase_gate(),
                    expected_raw_archive_sha256="0" * 64,
                )

    def test_undocumented_encoder_c_is_never_compared(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "fixture.zip"
            self.write_zip(archive, include_c=True)
            evidence = self.compare(archive)
        self.assertEqual(evidence["pair_count"], 1)
        self.assertNotIn("C", canonical_ab_comparison_json(evidence))

    def test_premature_gold_authorization_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "fixture.zip"
            self.write_zip(archive)
            gate = self.phrase_gate()
            gate["gold_assignment_authorized"] = True
            with self.assertRaises(TavernABComparisonError):
                self.compare(archive, gate)

    def test_encoder_directory_filename_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "fixture.zip"
            self.write_zip(archive, b_directory="Encoder_A")
            with self.assertRaises(TavernABComparisonError):
                self.compare(archive)

    def test_duplicate_analysis_member_fails_at_zip_security_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "fixture.zip"
            self.write_zip(archive, duplicate_a=True)
            with self.assertRaises(IngestSecurityError):
                self.compare(archive)

    def test_canonical_json_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "fixture.zip"
            self.write_zip(archive, a=b"I\n", b=b"V\n")
            evidence = self.compare(archive)
        left = canonical_ab_comparison_json(evidence)
        right = canonical_ab_comparison_json(copy.deepcopy(evidence))
        self.assertEqual(left, right)


if __name__ == "__main__":
    unittest.main()
