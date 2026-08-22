from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from st_harmonic_training.tavern_normalization_adapter import (
    TavernNormalizationAdapterError,
    build_tavern_normalized_targets,
    canonical_tavern_normalized_targets_json,
    parse_tavern_analysis_label,
)
from st_harmonic_training.tavern_structure import PINNED_TAVERN_REVISION


class TavernNormalizationParserTests(unittest.TestCase):
    def test_chords_and_function_are_preserved_as_source_sequences(self) -> None:
        raw = "**chords\t**function\n*c:\t*c:\n4i\t4T\n2.V65\t2.D\n4i\t4T\n*-\t*-\n"
        mapping, metadata = parse_tavern_analysis_label(raw)
        self.assertEqual(mapping["key"], "c:")
        self.assertEqual(mapping["roman_numeral"], '["i","V65","i"]')
        self.assertEqual(mapping["phrase"], '["T","D","T"]')
        self.assertIsNone(mapping["inversion"])
        self.assertIsNone(mapping["chord_family"])
        self.assertEqual(metadata["harmonic_spine"], "**chords")
        self.assertTrue(metadata["function_spine_present"])

    def test_undocumented_function_codes_remain_literal(self) -> None:
        raw = "**harm\t**function\n*C:\t*C:\n4I\t4PD\n4V\t4A\n*-\t*-\n"
        mapping, _ = parse_tavern_analysis_label(raw)
        self.assertEqual(mapping["phrase"], '["PD","A"]')

    def test_function_spine_is_optional(self) -> None:
        raw = "**harm\n*C:\n4I\n2V7\n*-\n"
        mapping, metadata = parse_tavern_analysis_label(raw)
        self.assertEqual(mapping["roman_numeral"], '["I","V7"]')
        self.assertIsNone(mapping["phrase"])
        self.assertFalse(metadata["function_spine_present"])

    def test_key_changes_are_literal_sequence_not_inferred_modulation(self) -> None:
        raw = "**chords\n*D:\n4I\n*Ab:\n4V\n*D:\n4I\n*-\n"
        mapping, metadata = parse_tavern_analysis_label(raw)
        self.assertEqual(mapping["key"], "D:")
        self.assertEqual(mapping["local_key"], '["Ab:","D:"]')
        self.assertEqual(metadata["explicit_key_count"], 3)

    def test_no_harmonic_data_fails_closed(self) -> None:
        raw = "**harm\t**function\n*C:\t*C:\n.\t4T\n*-\t*-\n"
        with self.assertRaises(TavernNormalizationAdapterError):
            parse_tavern_analysis_label(raw)


class TavernNormalizationBuilderTests(unittest.TestCase):
    def _archive(self, root: Path, raw: bytes) -> tuple[Path, str, str]:
        member = "TAVERN-master/Beethoven/B063/Encodings/Encoder_B/B063_00_01_encoderB.krn"
        path = root / "tavern.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(member, raw)
        return path, member, hashlib.sha256(path.read_bytes()).hexdigest()

    def _realization(self, member: str, raw: bytes) -> dict[str, object]:
        return {
            "schema_version": "st-tavern-raw-label-realization-v1",
            "source_corpus": "TAVERN_REVIEWED_694",
            "source_revision": PINNED_TAVERN_REVISION,
            "archive_sha256": "ARCHIVE",
            "validated_human_decisions_sha256": "DECISIONS",
            "record_count": 1,
            "selected_label_count": 1,
            "records": [
                {
                    "phrase_key": "Beethoven/B063:00:01",
                    "decision": "SELECT_B",
                    "selected_labels": [
                        {
                            "source": "B",
                            "archive_member": member,
                            "raw_sha256": hashlib.sha256(raw).hexdigest(),
                            "byte_count": len(raw),
                        }
                    ],
                }
            ],
            "raw_label_realization_complete": True,
            "normalization_complete": False,
            "training_authorized": False,
        }

    def _build(self, raw: bytes, *, mutate=None) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as tmp:
            archive, member, archive_sha = self._archive(Path(tmp), raw)
            realization = self._realization(member, raw)
            realization["archive_sha256"] = archive_sha
            realization["validated_human_decisions_sha256"] = "a" * 64
            if mutate is not None:
                mutate(realization)
            return build_tavern_normalized_targets(
                realization,
                archive_path=archive,
                expected_record_count=1,
                expected_selected_label_count=1,
                expected_archive_sha256=archive_sha,
                expected_decision_sha256="a" * 64,
            )

    def test_builder_hash_verifies_and_keeps_training_disabled(self) -> None:
        raw = b"**chords\t**function\n*c:\t*c:\n4i\t4T\n2V7\t2D\n*-\t*-\n"
        result = self._build(raw)
        self.assertEqual(result["record_count"], 1)
        self.assertEqual(result["normalized_target_count"], 1)
        target = result["records"][0]["targets"][0]["normalized_st_label"]
        self.assertEqual(target["key"], "c:")
        self.assertEqual(target["roman_numeral"], '["i","V7"]')
        self.assertTrue(result["normalization_complete"])
        self.assertFalse(result["partition_assignment_authorized"])
        self.assertFalse(result["training_authorized"])

    def test_raw_hash_tamper_fails_closed(self) -> None:
        raw = b"**harm\n*C:\n4I\n*-\n"
        def mutate(data):
            data["records"][0]["selected_labels"][0]["raw_sha256"] = "b" * 64
        with self.assertRaises(TavernNormalizationAdapterError):
            self._build(raw, mutate=mutate)

    def test_upstream_training_authority_escalation_fails_closed(self) -> None:
        raw = b"**harm\n*C:\n4I\n*-\n"
        with self.assertRaises(TavernNormalizationAdapterError):
            self._build(raw, mutate=lambda data: data.__setitem__("training_authorized", True))

    def test_selected_source_must_agree_with_human_decision(self) -> None:
        raw = b"**harm\n*C:\n4I\n*-\n"
        def mutate(data):
            data["records"][0]["decision"] = "SELECT_A"
        with self.assertRaises(TavernNormalizationAdapterError):
            self._build(raw, mutate=mutate)

    def test_output_is_deterministic(self) -> None:
        raw = b"**harm\t**function\n*C:\t*C:\n4I\t4T\n2V7\t2D\n*-\t*-\n"
        left = self._build(raw)
        right = self._build(raw)
        self.assertEqual(
            canonical_tavern_normalized_targets_json(left),
            canonical_tavern_normalized_targets_json(right),
        )


if __name__ == "__main__":
    unittest.main()
