from __future__ import annotations

import unittest

from st_harmonic_training.dedup import (
    DedupRecord,
    detect_duplicate_pairs,
    symbolic_fingerprint,
    transposition_invariant_pitch_tokens,
)
from st_harmonic_training.identity import WorkIdentity
from st_harmonic_training.split import (
    Partition,
    SplitRecord,
    assert_training_label_access,
    augmentation_allowed,
    deterministic_partition,
    leakage_violations,
)


def identity(record_id: str, *, corpus: str = "A", work: str = "work-1", duplicate: str = "dup-1", parent: str | None = None, split_group: str = "group-1") -> WorkIdentity:
    return WorkIdentity(
        record_id=record_id,
        source_corpus=corpus,
        source_record_id=f"src-{record_id}",
        canonical_work_id=work,
        edition_id=f"ed-{record_id}",
        duplicate_cluster_id=duplicate,
        derivation_parent_id=parent,
        split_group_id=split_group,
    )


class IdentityDedupTests(unittest.TestCase):
    def test_transpositions_share_interval_fingerprint(self) -> None:
        a = transposition_invariant_pitch_tokens([60, 64, 67, 72])
        b = transposition_invariant_pitch_tokens([62, 66, 69, 74])
        self.assertEqual(symbolic_fingerprint(a), symbolic_fingerprint(b))

    def test_cross_corpus_exact_symbolic_duplicate_is_detected(self) -> None:
        records = [
            DedupRecord(identity("a", corpus="DCML"), "Composer", "Piece", "", ("0", "4", "3")),
            DedupRecord(identity("b", corpus="ChoCo"), "Different metadata", "Renamed", "", ("0", "4", "3")),
        ]
        pairs = detect_duplicate_pairs(records)
        self.assertEqual(len(pairs), 1)
        self.assertTrue(pairs[0].exact_symbolic_match)
        self.assertTrue(pairs[0].cross_corpus)

    def test_metadata_match_alone_is_not_enough(self) -> None:
        records = [
            DedupRecord(identity("a"), "Composer", "Piece", "Op. 1", ("a", "b", "c", "d")),
            DedupRecord(identity("b", duplicate="dup-2", split_group="group-2"), "Composer", "Piece", "Op. 1", ("x", "y", "z", "q")),
        ]
        self.assertEqual(detect_duplicate_pairs(records), [])


class SplitSafetyTests(unittest.TestCase):
    def test_split_is_deterministic_by_group(self) -> None:
        first = deterministic_partition("same-work-family")
        second = deterministic_partition("same-work-family")
        self.assertIs(first, second)

    def test_augmentation_is_train_only(self) -> None:
        self.assertTrue(augmentation_allowed(Partition.TRAIN))
        for partition in Partition:
            if partition is not Partition.TRAIN:
                self.assertFalse(augmentation_allowed(partition))

    def test_training_label_access_is_train_only(self) -> None:
        assert_training_label_access(Partition.TRAIN)
        for partition in (Partition.VALIDATION, Partition.CALIBRATION, Partition.HOLDOUT, Partition.EXTERNAL_HOLDOUT):
            with self.assertRaises(PermissionError):
                assert_training_label_access(partition)

    def test_work_family_cross_split_is_rejected(self) -> None:
        records = [
            SplitRecord(identity("a"), Partition.TRAIN),
            SplitRecord(identity("b"), Partition.HOLDOUT),
        ]
        violations = leakage_violations(records)
        self.assertTrue(any(item.startswith("work:work-1") for item in violations))
        self.assertTrue(any(item.startswith("duplicate:dup-1") for item in violations))
        self.assertTrue(any(item.startswith("split:group-1") for item in violations))

    def test_derivation_parent_cross_split_is_rejected(self) -> None:
        parent = identity("parent", work="w1", duplicate="d1", split_group="g1")
        child = identity("child", work="w2", duplicate="d2", parent="parent", split_group="g2")
        violations = leakage_violations([
            SplitRecord(parent, Partition.TRAIN),
            SplitRecord(child, Partition.VALIDATION),
        ])
        self.assertTrue(any(item.startswith("derivation:parent->child") for item in violations))


if __name__ == "__main__":
    unittest.main()
