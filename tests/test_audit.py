from __future__ import annotations

from dataclasses import replace
import unittest

from st_harmonic_training.audit import AuditSample, audit_dataset
from st_harmonic_training.contracts import (
    AdjudicationOutcome,
    GoldTier,
    SourceManifest,
)
from st_harmonic_training.identity import WorkIdentity
from st_harmonic_training.normalization import NORMALIZATION_VERSION
from st_harmonic_training.split import Partition


def ready_source() -> SourceManifest:
    return SourceManifest.from_dict({
        "source_corpus": "example",
        "source_url": "https://example.invalid/corpus",
        "immutable_revision": "commit:0123456789abcdef",
        "release_tag_commit_doi": "commit:0123456789abcdef",
        "raw_archive_sha256": "a" * 64,
        "score_sha256": "b" * 64,
        "analysis_sha256": "c" * 64,
        "license_id": "CC-BY-4.0",
        "license_scope": "scores and annotations",
        "source_provenance": "test fixture",
        "annotation_provenance": "human test fixture",
        "known_issues": [],
        "acquisition_status": "READY",
        "quarantine_reason": None,
    })


def sample(index: int, partition: Partition) -> AuditSample:
    identity = WorkIdentity(
        record_id=f"r{index}",
        source_corpus="example",
        source_record_id=f"source-{index}",
        canonical_work_id=f"work-{index}",
        edition_id=f"edition-{index}",
        duplicate_cluster_id=f"dup-{index}",
        derivation_parent_id=None,
        split_group_id=f"group-{index}",
    )
    return AuditSample(
        identity=identity,
        partition=partition,
        gold_tier=GoldTier.GOLD_EXPERT,
        adjudication_outcome=AdjudicationOutcome.RESOLVED,
        class_label="V" if index % 2 else "I",
        annotation_provenance="human expert",
        normalization_version=NORMALIZATION_VERSION,
        file_status="OK",
    )


class AuditTests(unittest.TestCase):
    def passing_samples(self) -> list[AuditSample]:
        return [
            sample(1, Partition.TRAIN),
            sample(2, Partition.VALIDATION),
            sample(3, Partition.CALIBRATION),
            sample(4, Partition.HOLDOUT),
        ]

    def test_complete_synthetic_dataset_passes(self) -> None:
        report = audit_dataset(
            candidate_sources=["example"],
            source_manifests=[ready_source()],
            samples=self.passing_samples(),
        )
        self.assertTrue(report.training_authorized)
        self.assertEqual(report.blockers, ())

    def test_empty_real_state_holds_training(self) -> None:
        report = audit_dataset(
            candidate_sources=["DCML corpora"],
            source_manifests=[],
            samples=[],
        )
        self.assertFalse(report.training_authorized)
        self.assertIn("NO_READY_SOURCE", report.blockers)
        self.assertIn("NO_ELIGIBLE_SAMPLES", report.blockers)
        self.assertIn("DCML corpora", report.candidate_sources_missing_manifests)

    def test_cross_split_work_leakage_blocks_training(self) -> None:
        samples = self.passing_samples()
        leaked_identity = replace(
            samples[1].identity,
            canonical_work_id=samples[0].identity.canonical_work_id,
        )
        samples[1] = replace(samples[1], identity=leaked_identity)
        report = audit_dataset(
            candidate_sources=["example"],
            source_manifests=[ready_source()],
            samples=samples,
        )
        self.assertFalse(report.training_authorized)
        self.assertTrue(any(item.startswith("LEAKAGE:work:") for item in report.blockers))

    def test_missing_normalization_version_blocks_training(self) -> None:
        samples = self.passing_samples()
        samples[0] = replace(samples[0], normalization_version=None)
        report = audit_dataset(
            candidate_sources=["example"],
            source_manifests=[ready_source()],
            samples=samples,
        )
        self.assertFalse(report.training_authorized)
        self.assertIn("NORMALIZATION_VERSION_MISSING_OR_INVALID:r1", report.blockers)

    def test_quarantine_is_reported_but_excluded_from_required_split_logic(self) -> None:
        samples = self.passing_samples()
        quarantined = replace(
            sample(5, Partition.QUARANTINE),
            gold_tier=GoldTier.QUARANTINE,
            normalization_version=None,
        )
        report = audit_dataset(
            candidate_sources=["example"],
            source_manifests=[ready_source()],
            samples=samples + [quarantined],
        )
        self.assertTrue(report.training_authorized)
        self.assertEqual(report.quarantined_sample_count, 1)


if __name__ == "__main__":
    unittest.main()
