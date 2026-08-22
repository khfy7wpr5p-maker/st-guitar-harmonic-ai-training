from __future__ import annotations

import unittest

from st_harmonic_training.tavern_lineage_closure import (
    TavernLineageClosureError,
    build_tavern_reviewed_lineage_closure,
    canonical_tavern_reviewed_lineage_closure_json,
)
from st_harmonic_training.tavern_structure import PINNED_TAVERN_REVISION


class TavernLineageClosureTests(unittest.TestCase):
    def payload(self) -> dict[str, object]:
        works = sorted({
            "Beethoven/B063","Beethoven/B064","Beethoven/B065","Beethoven/B066","Beethoven/B068","Beethoven/B069",
            "Beethoven/B070","Beethoven/B072","Beethoven/B073","Beethoven/B075","Beethoven/B076","Beethoven/B077",
            "Beethoven/B078","Beethoven/B080","Beethoven/Opus34","Beethoven/Opus76","Mozart/K265","Mozart/K353",
            "Mozart/K354","Mozart/K398","Mozart/K455","Mozart/K501","Mozart/K573","Mozart/K613",
        })
        decisions = [{"phrase_key": f"{work}:00:01"} for work in works]
        return {
            "schema_version": "st-tavern-human-adjudication-v1",
            "source_corpus": "TAVERN",
            "source_revision": PINNED_TAVERN_REVISION,
            "decisions": decisions,
        }

    def build(self) -> dict[str, object]:
        data = self.payload()
        return build_tavern_reviewed_lineage_closure(
            data, artifact_sha256="a" * 64,
            expected_artifact_sha256="a" * 64, expected_count=len(data["decisions"]),
        )

    def test_24_reviewed_work_families_are_bound(self) -> None:
        result = self.build()
        self.assertEqual(result["active_work_family_count"], 24)
        self.assertEqual(result["inactive_documented_work_ids"], ["Beethoven/B071", "Mozart/K025", "Mozart/K179"])
        self.assertTrue(result["cross_corpus_aliases_bound"])
        self.assertFalse(result["partition_assignment_authorized"])
        self.assertFalse(result["training_authorized"])
        self.assertTrue(all(x["alias_partition_inheritance_required"] for x in result["families"]))

    def test_unknown_work_fails_closed(self) -> None:
        data = self.payload(); data["decisions"][0]["phrase_key"] = "Mozart/K999:00:01"
        with self.assertRaises(TavernLineageClosureError):
            build_tavern_reviewed_lineage_closure(data, artifact_sha256="a"*64, expected_artifact_sha256="a"*64, expected_count=24)

    def test_duplicate_phrase_fails_closed(self) -> None:
        data = self.payload(); data["decisions"].append(dict(data["decisions"][0]))
        with self.assertRaises(TavernLineageClosureError):
            build_tavern_reviewed_lineage_closure(data, artifact_sha256="a"*64, expected_artifact_sha256="a"*64, expected_count=25)

    def test_digest_mismatch_fails_closed(self) -> None:
        data = self.payload()
        with self.assertRaises(TavernLineageClosureError):
            build_tavern_reviewed_lineage_closure(data, artifact_sha256="a"*64, expected_artifact_sha256="b"*64, expected_count=24)

    def test_deterministic_output(self) -> None:
        self.assertEqual(
            canonical_tavern_reviewed_lineage_closure_json(self.build()),
            canonical_tavern_reviewed_lineage_closure_json(self.build()),
        )


if __name__ == "__main__":
    unittest.main()
