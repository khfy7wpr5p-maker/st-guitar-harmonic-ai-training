from __future__ import annotations

import unittest

from st_harmonic_training.contracts import ContractError, GoldRecord, SourceManifest


GOOD_SHA = "a" * 64


def ready_source() -> dict:
    return {
        "source_corpus": "example",
        "source_url": "https://example.invalid/corpus",
        "immutable_revision": "commit:0123456789abcdef",
        "release_tag_commit_doi": "commit:0123456789abcdef",
        "raw_archive_sha256": GOOD_SHA,
        "score_sha256": "b" * 64,
        "analysis_sha256": "c" * 64,
        "license_id": "CC-BY-4.0",
        "license_scope": "scores and annotations",
        "source_provenance": "upstream release",
        "annotation_provenance": "upstream human analysis",
        "known_issues": [],
        "acquisition_status": "READY",
        "quarantine_reason": None,
    }


class SourceManifestTests(unittest.TestCase):
    def test_ready_manifest_accepts_complete_evidence(self) -> None:
        manifest = SourceManifest.from_dict(ready_source())
        self.assertEqual(manifest.source_corpus, "example")

    def test_ready_manifest_rejects_missing_hash(self) -> None:
        data = ready_source()
        data["analysis_sha256"] = None
        with self.assertRaises(ContractError):
            SourceManifest.from_dict(data)

    def test_ready_manifest_rejects_unresolved_license(self) -> None:
        data = ready_source()
        data["license_id"] = "UNRESOLVED"
        with self.assertRaises(ContractError):
            SourceManifest.from_dict(data)

    def test_quarantine_requires_reason(self) -> None:
        data = ready_source()
        data.update({
            "acquisition_status": "QUARANTINE",
            "raw_archive_sha256": None,
            "score_sha256": None,
            "analysis_sha256": None,
            "license_id": "UNRESOLVED",
            "quarantine_reason": None,
        })
        with self.assertRaises(ContractError):
            SourceManifest.from_dict(data)


class GoldTierTests(unittest.TestCase):
    def test_auto_annotation_cannot_be_teacher_gold(self) -> None:
        with self.assertRaises(ContractError):
            GoldRecord.from_dict({
                "record_id": "x",
                "gold_tier": "GOLD_EXPERT",
                "annotation_kind": "AUTO",
                "adjudication_outcome": "RESOLVED",
                "raw_source_label": "V7",
                "annotator_count": 0,
            })

    def test_ambiguous_human_variant_is_preserved(self) -> None:
        record = GoldRecord.from_dict({
            "record_id": "x",
            "gold_tier": "GOLD_VARIANT",
            "annotation_kind": "HUMAN_VARIANT",
            "adjudication_outcome": "AMBIGUOUS",
            "raw_source_label": "V/ii | Ger+6",
            "annotator_count": 2,
        })
        self.assertEqual(record.adjudication_outcome.value, "AMBIGUOUS")

    def test_auto_only_cannot_establish_gold_ambiguity(self) -> None:
        with self.assertRaises(ContractError):
            GoldRecord.from_dict({
                "record_id": "x",
                "gold_tier": "SILVER_AUTO",
                "annotation_kind": "AUTO",
                "adjudication_outcome": "AMBIGUOUS",
                "raw_source_label": "V7",
                "annotator_count": 0,
            })


if __name__ == "__main__":
    unittest.main()
