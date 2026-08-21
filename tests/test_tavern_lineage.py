from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from st_harmonic_training.tavern_lineage import (
    EXPECTED_SOURCE_WORK_IDS,
    TavernLineageError,
    build_tavern_lineage_evidence,
    canonical_lineage_json,
)


STRUCTURE_PATH = Path("evidence/tavern/stage0i_tavern_structure.v1.json")


class TavernLineageTests(unittest.TestCase):
    def load_structure(self) -> dict[str, object]:
        return json.loads(STRUCTURE_PATH.read_text(encoding="utf-8"))

    def test_committed_structure_maps_exactly_27_work_families(self) -> None:
        evidence = build_tavern_lineage_evidence(self.load_structure())
        self.assertEqual(evidence["work_family_count"], 27)
        self.assertEqual(
            [item["source_work_id"] for item in evidence["work_families"]],
            list(EXPECTED_SOURCE_WORK_IDS),
        )

    def test_b063_lineage_aliases_are_explicit(self) -> None:
        evidence = build_tavern_lineage_evidence(self.load_structure())
        record = next(
            item for item in evidence["work_families"]
            if item["source_work_id"] == "Beethoven/B063"
        )
        self.assertEqual(record["canonical_work_id"], "st-work:beethoven:woo63")
        self.assertEqual(record["split_group_id"], "st-work:beethoven:woo63")
        self.assertEqual(
            record["aliases"]["When-in-Rome"],
            ["Corpus/Variations_and_Grounds/Beethoven,_Ludwig_van/_/WoO_63"],
        )
        self.assertEqual(
            record["aliases"]["AugmentedNet"],
            ["tavern-beethoven-woo-63-a", "tavern-beethoven-woo-63-b"],
        )

    def test_opus_and_mozart_catalogue_mapping_is_stable(self) -> None:
        evidence = build_tavern_lineage_evidence(self.load_structure())
        by_id = {item["source_work_id"]: item for item in evidence["work_families"]}
        self.assertEqual(
            by_id["Beethoven/Opus34"]["aliases"]["When-in-Rome"],
            ["Corpus/Variations_and_Grounds/Beethoven,_Ludwig_van/_/Op34"],
        )
        self.assertEqual(
            by_id["Mozart/K025"]["aliases"]["AugmentedNet"],
            ["tavern-mozart-k025-a", "tavern-mozart-k025-b"],
        )

    def test_lineage_does_not_authorize_partition_or_training(self) -> None:
        evidence = build_tavern_lineage_evidence(self.load_structure())
        self.assertFalse(evidence["partition_assignment_authorized"])
        self.assertFalse(evidence["training_authorized"])
        self.assertIn(
            "PHRASE_STRUCTURE_RECONCILIATION_REQUIRED",
            evidence["remaining_blockers"],
        )
        self.assertIn(
            "TEACHER_GOLD_ADJUDICATION_REQUIRED",
            evidence["remaining_blockers"],
        )

    def test_missing_work_fails_closed(self) -> None:
        structure = self.load_structure()
        structure["work_summaries"] = structure["work_summaries"][:-1]
        with self.assertRaises(TavernLineageError):
            build_tavern_lineage_evidence(structure)

    def test_preassigned_identity_fails_closed(self) -> None:
        structure = self.load_structure()
        structure["work_summaries"][0]["canonical_work_id"] = "preassigned"
        with self.assertRaises(TavernLineageError):
            build_tavern_lineage_evidence(structure)

    def test_non_quarantine_prelineage_partition_fails_closed(self) -> None:
        structure = self.load_structure()
        structure["work_summaries"][0]["partition"] = "TRAIN"
        with self.assertRaises(TavernLineageError):
            build_tavern_lineage_evidence(structure)

    def test_canonical_and_split_ids_are_unique(self) -> None:
        evidence = build_tavern_lineage_evidence(self.load_structure())
        canonical = [item["canonical_work_id"] for item in evidence["work_families"]]
        split_ids = [item["split_group_id"] for item in evidence["work_families"]]
        self.assertEqual(len(canonical), len(set(canonical)))
        self.assertEqual(len(split_ids), len(set(split_ids)))

    def test_canonical_json_is_deterministic(self) -> None:
        structure = self.load_structure()
        left = canonical_lineage_json(build_tavern_lineage_evidence(structure))
        right = canonical_lineage_json(
            build_tavern_lineage_evidence(copy.deepcopy(structure))
        )
        self.assertEqual(left, right)


if __name__ == "__main__":
    unittest.main()
