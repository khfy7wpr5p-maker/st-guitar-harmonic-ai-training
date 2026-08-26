from __future__ import annotations

import copy
import subprocess
import sys
import unittest
from pathlib import Path

from st_harmonic_training.stage1e_internal_cv import (
    FOLD_COUNT,
    PINNED_GROUP_PLAN_SHA256,
)
from st_harmonic_training.stage2b_specialist_materialization import (
    MATERIALIZATION_SCHEMA,
    SPECIALIST_FIELDS,
    SUMMARY_SCHEMA,
    TARGET_SET_POLICY,
    Stage2BSpecialistMaterializationError,
    build_stage2b_summary,
    build_train_identity_map,
    project_specialist_targets,
)
from st_harmonic_training.tavern_reviewed_split import SPLIT_SCHEMA
from st_harmonic_training.tavern_structure import PINNED_TAVERN_REVISION


class Stage2BSpecialistMaterializationTests(unittest.TestCase):
    def group_plan(self) -> dict[str, object]:
        groups = [
            {
                "split_group_id": f"work-{index:02d}",
                "development_fold": index % FOLD_COUNT,
            }
            for index in range(18)
        ]
        return {
            "group_plan_manifest_sha256": PINNED_GROUP_PLAN_SHA256,
            "fold_count": FOLD_COUNT,
            "eligible_partition": "TRAIN",
            "groups": groups,
            "original_validation_access": False,
            "calibration_access": False,
            "holdout_access": False,
            "training_authorized": False,
            "production_authority": False,
        }

    def reviewed_split(self) -> tuple[dict[str, object], dict[str, int]]:
        records: list[dict[str, object]] = []
        for index in range(18):
            source = f"Source{index:02d}"
            group = f"work-{index:02d}"
            records.append(
                {
                    "phrase_key": f"{source}:00:01",
                    "source_work_id": source,
                    "canonical_work_id": group,
                    "split_group_id": group,
                    "partition": "TRAIN",
                }
            )
        for partition, suffix in (
            ("VALIDATION", "V"),
            ("CALIBRATION", "C"),
            ("HOLDOUT", "H"),
        ):
            records.append(
                {
                    "phrase_key": f"Source{suffix}:00:01",
                    "source_work_id": f"Source{suffix}",
                    "canonical_work_id": f"work-{suffix}",
                    "split_group_id": f"work-{suffix}",
                    "partition": partition,
                }
            )
        distribution = {
            "CALIBRATION": 1,
            "HOLDOUT": 1,
            "TRAIN": 18,
            "VALIDATION": 1,
        }
        return (
            {
                "schema_version": SPLIT_SCHEMA,
                "source_corpus": "TAVERN_REVIEWED_694",
                "source_revision": PINNED_TAVERN_REVISION,
                "record_distribution": distribution,
                "records": records,
                "training_authorized": False,
            },
            distribution,
        )

    def fake_materialization(self) -> dict[str, object]:
        return {
            "schema_version": MATERIALIZATION_SCHEMA,
            "source_corpus": "TAVERN_REVIEWED_694",
            "source_revision": PINNED_TAVERN_REVISION,
            "validated_human_decisions_sha256": "a" * 64,
            "archive_sha256": "b" * 64,
            "score_inventory_sha256": "c" * 64,
            "score_inventory_member_count": 100,
            "eligible_original_partition": "TRAIN",
            "record_count": 487,
            "work_family_count": 18,
            "fold_count": 3,
            "group_plan_manifest_sha256": PINNED_GROUP_PLAN_SHA256,
            "fold_record_distribution": {"0": 160, "1": 161, "2": 166},
            "fold_work_family_distribution": {"0": 6, "1": 6, "2": 6},
            "source_target_slot_count": 500,
            "specialist_support": {
                specialist_id: {
                    "supported_source_target_count": 400,
                    "effective_target_count": 390,
                    "eligible_record_count": 380,
                    "missing_record_count": 107,
                }
                for specialist_id, _field in SPECIALIST_FIELDS
            },
            "feature_adapter_version": "st-tavern-kern-bow-v1",
            "feature_vocabulary_count": 123,
            "feature_occurrence_count": 456,
            "target_set_policy": TARGET_SET_POLICY,
            "annotation_parse_scope": "TRAIN_ONLY",
            "score_feature_scope": "TRAIN_ONLY",
            "private_record_manifest_sha256": "d" * 64,
            "records": [{"private": True}],
            "non_train_annotation_bodies_materialized": False,
            "original_validation_target_access": False,
            "calibration_target_access": False,
            "holdout_target_access": False,
            "event_level_training_authorized": False,
            "model_training_started": False,
            "training_authorized": False,
            "production_authority": False,
            "deterministic_resolver_remains_authoritative": True,
        }

    def test_identity_boundary_selects_train_only(self) -> None:
        split, distribution = self.reviewed_split()
        result = build_train_identity_map(
            split,
            expected_train_record_count=18,
            expected_record_distribution=distribution,
            group_plan=self.group_plan(),
        )
        self.assertEqual(len(result), 18)
        self.assertTrue(all(key.startswith("Source") for key in result))
        self.assertNotIn("SourceV:00:01", result)
        self.assertNotIn("SourceC:00:01", result)
        self.assertNotIn("SourceH:00:01", result)
        self.assertEqual(
            {int(item["development_fold"]) for item in result.values()},
            {0, 1, 2},
        )

    def test_identity_boundary_rejects_authority_escalation(self) -> None:
        split, distribution = self.reviewed_split()
        split["training_authorized"] = True
        with self.assertRaises(Stage2BSpecialistMaterializationError):
            build_train_identity_map(
                split,
                expected_train_record_count=18,
                expected_record_distribution=distribution,
                group_plan=self.group_plan(),
            )

    def test_identity_boundary_rejects_unknown_train_group(self) -> None:
        split, distribution = self.reviewed_split()
        split["records"][0]["split_group_id"] = "not-in-plan"
        split["records"][0]["canonical_work_id"] = "not-in-plan"
        with self.assertRaises(Stage2BSpecialistMaterializationError):
            build_train_identity_map(
                split,
                expected_train_record_count=18,
                expected_record_distribution=distribution,
                group_plan=self.group_plan(),
            )

    def test_specialist_projection_preserves_sources_and_deduplicates_effective_values(self) -> None:
        normalized = {
            "roman_numeral": '["V","I"]',
            "key": "C:",
            "phrase": '["D","T"]',
        }
        rows = [
            {"source": "A", "normalized_st_label": copy.deepcopy(normalized)},
            {"source": "B", "normalized_st_label": copy.deepcopy(normalized)},
        ]
        result = project_specialist_targets(rows)
        for specialist_id, _field in SPECIALIST_FIELDS:
            payload = result[specialist_id]
            self.assertEqual(len(payload["source_targets"]), 2)
            self.assertEqual(len(payload["effective_targets"]), 1)

    def test_specialist_projection_keeps_missing_key_and_function_explicit(self) -> None:
        rows = [
            {
                "source": "A",
                "normalized_st_label": {
                    "roman_numeral": '["I"]',
                    "key": None,
                    "phrase": None,
                },
            }
        ]
        result = project_specialist_targets(rows)
        self.assertEqual(
            result["ROMAN_NUMERAL_SPECIALIST"]["effective_targets"], ['["I"]']
        )
        self.assertEqual(result["KEY_SPECIALIST"]["effective_targets"], [])
        self.assertEqual(result["FUNCTION_SPECIALIST"]["effective_targets"], [])
        self.assertIsNone(result["KEY_SPECIALIST"]["source_targets"][0]["value"])

    def test_summary_does_not_expose_private_records(self) -> None:
        summary = build_stage2b_summary(self.fake_materialization())
        self.assertEqual(summary["schema_version"], SUMMARY_SCHEMA)
        self.assertNotIn("records", summary)
        self.assertTrue(summary["private_payload_external_only"])
        self.assertFalse(summary["training_authorized"])
        self.assertFalse(summary["original_validation_target_access"])
        self.assertFalse(summary["calibration_target_access"])
        self.assertFalse(summary["holdout_target_access"])

    def test_summary_rejects_non_train_access_escalation(self) -> None:
        data = self.fake_materialization()
        data["original_validation_target_access"] = True
        with self.assertRaises(Stage2BSpecialistMaterializationError):
            build_stage2b_summary(data)

    def test_direct_cli_help_bootstraps_repository_imports(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "scripts/materialize_stage2b_specialist_train.py", "--help"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Stage 2-B", result.stdout)


if __name__ == "__main__":
    unittest.main()
