from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from scripts.materialize_stage2g_function_onset_events import (
    Stage2GFunctionOnsetEventHandoffError,
    _assert_external_output_dir,
    _assert_new_outputs,
)
from st_harmonic_training.offline_experiment import LOCKED_PYTHON
from st_harmonic_training.stage1e_internal_cv import PINNED_GROUP_PLAN_SHA256
from st_harmonic_training.stage2g_function_onset_events import (
    CARRIER_AUTHORITY,
    EXPECTED_FOLD_CANDIDATE_RECORD_DISTRIBUTION,
    EXPECTED_FOLD_FUNCTION_ELIGIBLE_RECORD_DISTRIBUTION,
    EXPECTED_FOLD_RECORD_DISTRIBUTION,
    EXPECTED_FOLD_WORK_FAMILY_DISTRIBUTION,
    EXPECTED_FUNCTION_ELIGIBLE_RECORD_COUNT,
    EXPECTED_FUNCTION_SUPPORTED_SOURCE_TARGET_COUNT,
    EXPECTED_ONSET_CANDIDATE_RECORD_COUNT,
    EXPECTED_ONSET_CANDIDATE_SOURCE_PATH_COUNT,
    EXPECTED_QUARANTINE_RECORD_COUNT,
    EXPECTED_QUARANTINE_SOURCE_PATH_COUNT,
    EXPECTED_TRAIN_RECORD_COUNT,
    FUNCTION_SPECIALIST_TARGET_SHAPE,
    MATERIALIZATION_SCHEMA,
    PINNED_STAGE2F_DIAGNOSTIC_MANIFEST_SHA256,
    REJECTED_TARGET_SHAPES,
    Stage2GFunctionOnsetEventError,
    TARGET_AUTHORITY,
    _append_unique_events,
    _assert_target_partition,
    _canonical_sha256,
    _claim_unique_source_path,
    _materialize_candidate_record_events,
    _parse_onset_event_targets,
    _validate_fold_safety,
    build_stage2g_contract,
    build_stage2g_summary,
    load_and_validate_stage2f_private_receipt,
    validate_stage2g_contract,
)
from st_harmonic_training.stage2c_contract import (
    PINNED_STAGE2B_PRIVATE_RECORD_MANIFEST_SHA256,
    PINNED_STAGE2B_SOURCE_TARGET_SLOT_COUNT,
)
from st_harmonic_training.tavern_gold_materialization import PINNED_VALIDATED_SHA256
from st_harmonic_training.tavern_raw_label_realization import (
    PINNED_TAVERN_ARCHIVE_SHA256,
)
from st_harmonic_training.tavern_structure import PINNED_TAVERN_REVISION


ROOT = Path(__file__).resolve().parents[1]


def _encoder() -> str:
    return (
        "**harm\t**function\n"
        "*C:\t*\n"
        "4I\t4T\n"
        "4V\t4D\n"
        "*-\t*-\n"
    )


def _event_rows(source: str = "A") -> list[dict[str, object]]:
    return _parse_onset_event_targets(
        _encoder(),
        phrase_key="Mozart/K279:01:01",
        source=source,
        raw_sha256="a" * 64 if source == "A" else "b" * 64,
        split_group_id="Mozart/K279",
        development_fold=1,
    )


def _private_payload() -> dict[str, object]:
    events = _event_rows("A")
    return {
        "schema_version": MATERIALIZATION_SCHEMA,
        "source_corpus": "TAVERN_REVIEWED_694",
        "source_revision": PINNED_TAVERN_REVISION,
        "validated_human_decisions_sha256": PINNED_VALIDATED_SHA256,
        "archive_sha256": PINNED_TAVERN_ARCHIVE_SHA256,
        "source_stage1e_group_plan_manifest_sha256": PINNED_GROUP_PLAN_SHA256,
        "source_stage2b_private_record_manifest_sha256": (
            PINNED_STAGE2B_PRIVATE_RECORD_MANIFEST_SHA256
        ),
        "source_stage2f_diagnostic_manifest_sha256": (
            PINNED_STAGE2F_DIAGNOSTIC_MANIFEST_SHA256
        ),
        "eligible_original_partition": "TRAIN",
        "input_record_count": EXPECTED_TRAIN_RECORD_COUNT,
        "function_eligible_record_count": EXPECTED_FUNCTION_ELIGIBLE_RECORD_COUNT,
        "onset_carrier_candidate_record_count": EXPECTED_ONSET_CANDIDATE_RECORD_COUNT,
        "quarantine_record_count": EXPECTED_QUARANTINE_RECORD_COUNT,
        "selected_source_path_count": PINNED_STAGE2B_SOURCE_TARGET_SLOT_COUNT,
        "function_supported_source_target_count": (
            EXPECTED_FUNCTION_SUPPORTED_SOURCE_TARGET_COUNT
        ),
        "onset_carrier_candidate_source_path_count": (
            EXPECTED_ONSET_CANDIDATE_SOURCE_PATH_COUNT
        ),
        "quarantine_source_path_count": EXPECTED_QUARANTINE_SOURCE_PATH_COUNT,
        "materialized_source_path_count": EXPECTED_ONSET_CANDIDATE_SOURCE_PATH_COUNT,
        "fold_record_distribution": EXPECTED_FOLD_RECORD_DISTRIBUTION,
        "fold_function_eligible_record_distribution": (
            EXPECTED_FOLD_FUNCTION_ELIGIBLE_RECORD_DISTRIBUTION
        ),
        "fold_onset_carrier_candidate_record_distribution": (
            EXPECTED_FOLD_CANDIDATE_RECORD_DISTRIBUTION
        ),
        "fold_work_family_distribution": EXPECTED_FOLD_WORK_FAMILY_DISTRIBUTION,
        "materialized_event_count": len(events),
        "source_event_counts": {"A": len(events), "B": 0},
        "variant_provenance_counts": {
            "preserve_variants_train_record_count": 1,
            "preserve_variants_materialized_record_count": 1,
            "preserve_variants_materialized_source_path_count": 2,
        },
        "private_event_manifest_sha256": _canonical_sha256(events),
        "function_specialist_target_shape": FUNCTION_SPECIALIST_TARGET_SHAPE,
        "target_authority": TARGET_AUTHORITY,
        "carrier_authority": CARRIER_AUTHORITY,
        "events": events,
        "private_payload_external_only": True,
        "non_train_annotation_bodies_materialized": False,
        "original_validation_target_access": False,
        "calibration_target_access": False,
        "holdout_target_access": False,
        "stage1d_quarantine_reuse_authorized": False,
        "stage2f_quarantine_reuse_authorized": False,
        "duration_inference_used": False,
        "segment_boundary_inference_used": False,
        "joined_harmonic_labels_authoritative": False,
        "model_training_started": False,
        "model_selection_started": False,
        "full_train_final_fit_started": False,
        "event_level_training_authorized": False,
        "production_authority": False,
        "deterministic_resolver_remains_authoritative": True,
    }


class Stage2GFunctionOnsetEventTests(unittest.TestCase):
    def test_01_committed_contract_matches_builder(self) -> None:
        committed = json.loads(
            (
                ROOT / "evidence/stage2g_function_onset_event_contract.v1.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(committed, build_stage2g_contract())
        validate_stage2g_contract(committed)

    def test_02_private_stage2f_receipt_matches_frozen_evidence(self) -> None:
        receipt = load_and_validate_stage2f_private_receipt()
        self.assertEqual(
            receipt["diagnostic_manifest_sha256"],
            PINNED_STAGE2F_DIAGNOSTIC_MANIFEST_SHA256,
        )

    def test_03_target_shape_is_onset_event(self) -> None:
        self.assertEqual(
            build_stage2g_contract()["function_specialist_target_shape"],
            "ONSET_EVENT",
        )

    def test_04_retired_target_shapes_are_rejected(self) -> None:
        contract = build_stage2g_contract()
        self.assertEqual(contract["rejected_target_shapes"], list(REJECTED_TARGET_SHAPES))
        self.assertIn("WHOLE_PHRASE_SEQUENCE_AS_CLASS", REJECTED_TARGET_SHAPES)
        self.assertIn("SEGMENT_WITH_INFERRED_DURATION", REJECTED_TARGET_SHAPES)

    def test_05_only_train_partition_is_accepted(self) -> None:
        _assert_target_partition("TRAIN")

    def test_06_validation_partition_fails_closed(self) -> None:
        with self.assertRaises(Stage2GFunctionOnsetEventError):
            _assert_target_partition("VALIDATION")

    def test_07_calibration_partition_fails_closed(self) -> None:
        with self.assertRaises(Stage2GFunctionOnsetEventError):
            _assert_target_partition("CALIBRATION")

    def test_08_holdout_partition_fails_closed(self) -> None:
        with self.assertRaises(Stage2GFunctionOnsetEventError):
            _assert_target_partition("HOLDOUT")

    def test_09_stage1e_group_plan_hash_drift_fails_closed(self) -> None:
        fake = {
            "group_plan_manifest_sha256": "0" * 64,
            "groups": [],
        }
        with mock.patch(
            "st_harmonic_training.stage2g_function_onset_events.build_stage1e_group_plan",
            return_value=fake,
        ):
            with self.assertRaises(Stage2GFunctionOnsetEventError):
                build_stage2g_contract()

    def test_10_stage2f_manifest_pin_drift_fails_closed(self) -> None:
        with mock.patch(
            "st_harmonic_training.stage2g_function_onset_events."
            "PINNED_STAGE2F_DIAGNOSTIC_MANIFEST_SHA256",
            "0" * 64,
        ):
            with self.assertRaises(Stage2GFunctionOnsetEventError):
                load_and_validate_stage2f_private_receipt()

    def test_11_human_function_token_is_preserved_exactly(self) -> None:
        rows = _event_rows()
        self.assertEqual([row["function_token"] for row in rows], ["4T", "4D"])

    def test_12_function_target_requires_harmonic_onset_carrier(self) -> None:
        encoder = (
            "**harm\t**function\n"
            "4I\t4T\n"
            ".\t4D\n"
            "4V\t.\n"
            "*-\t*-\n"
        )
        with self.assertRaises(Stage2GFunctionOnsetEventError):
            _parse_onset_event_targets(
                encoder,
                phrase_key="Mozart/K279:01:01",
                source="A",
                raw_sha256="a" * 64,
                split_group_id="Mozart/K279",
                development_fold=0,
            )

    def test_13_missing_function_token_cannot_be_invented(self) -> None:
        encoder = "**harm\t**function\n4I\t.\n4V\t.\n*-\t*-\n"
        with self.assertRaises(Stage2GFunctionOnsetEventError):
            _parse_onset_event_targets(
                encoder,
                phrase_key="Mozart/K279:01:01",
                source="A",
                raw_sha256="a" * 64,
                split_group_id="Mozart/K279",
                development_fold=0,
            )

    def test_14_event_rows_have_no_inferred_duration_field(self) -> None:
        for row in _event_rows():
            self.assertNotIn("duration", row)
            self.assertNotIn("reciprocal", row)
            self.assertNotIn("end", row)

    def test_15_event_rows_have_no_segment_boundary_field(self) -> None:
        for row in _event_rows():
            self.assertNotIn("segment_start", row)
            self.assertNotIn("segment_end", row)
            self.assertNotIn("boundary", row)

    def test_16_joined_harmonic_labels_are_not_authority(self) -> None:
        self.assertIs(
            build_stage2g_contract()["joined_harmonic_labels_authoritative"],
            False,
        )

    def test_17_ab_source_provenance_is_preserved(self) -> None:
        a = _event_rows("A")[0]
        b = _event_rows("B")[0]
        self.assertEqual(a["source"], "A")
        self.assertEqual(b["source"], "B")
        self.assertNotEqual(a["carrier_event_id"], b["carrier_event_id"])

    def test_18_duplicate_source_path_fails_closed(self) -> None:
        seen: set[tuple[str, str]] = set()
        _claim_unique_source_path(seen, "x", "A")
        with self.assertRaises(Stage2GFunctionOnsetEventError):
            _claim_unique_source_path(seen, "x", "A")

    def test_19_duplicate_event_identity_fails_closed(self) -> None:
        event = _event_rows()[0]
        destination: list[dict[str, object]] = []
        seen: set[str] = set()
        _append_unique_events(destination, seen, [event])
        with self.assertRaises(Stage2GFunctionOnsetEventError):
            _append_unique_events(destination, seen, [event])

    def test_20_quarantine_record_cannot_materialize(self) -> None:
        source_rows = [
            {
                "source": "A",
                "raw_sha256": "a" * 64,
                "encoder_text": _encoder(),
                "status": "QUARANTINE",
            }
        ]
        with self.assertRaises(Stage2GFunctionOnsetEventError):
            _materialize_candidate_record_events(
                source_rows,
                phrase_key="Mozart/K279:01:01",
                split_group_id="Mozart/K279",
                development_fold=0,
            )

    def test_21_non_candidate_record_cannot_materialize(self) -> None:
        source_rows = [
            {
                "source": "A",
                "raw_sha256": "a" * 64,
                "encoder_text": _encoder(),
                "status": "FUNCTION_EVENTS_MISSING",
            }
        ]
        with self.assertRaises(Stage2GFunctionOnsetEventError):
            _materialize_candidate_record_events(
                source_rows,
                phrase_key="Mozart/K279:01:01",
                split_group_id="Mozart/K279",
                development_fold=0,
            )

    def test_22_candidate_record_materializes_ab_provenance(self) -> None:
        source_rows = [
            {
                "source": "A",
                "raw_sha256": "a" * 64,
                "encoder_text": _encoder(),
                "status": "FUNCTION_ONSET_CARRIER_CANDIDATE",
            },
            {
                "source": "B",
                "raw_sha256": "b" * 64,
                "encoder_text": _encoder(),
                "status": "FUNCTION_ONSET_CARRIER_CANDIDATE",
            },
        ]
        rows = _materialize_candidate_record_events(
            source_rows,
            phrase_key="Mozart/K279:01:01",
            split_group_id="Mozart/K279",
            development_fold=2,
        )
        self.assertEqual({row["source"] for row in rows}, {"A", "B"})
        self.assertTrue(all(row["development_fold"] == 2 for row in rows))

    def test_23_development_fold_drift_fails_closed(self) -> None:
        fake_plan = {
            "group_plan_manifest_sha256": PINNED_GROUP_PLAN_SHA256,
            "groups": [{"split_group_id": "work", "development_fold": 0}],
        }
        with mock.patch(
            "st_harmonic_training.stage2g_function_onset_events.build_stage1e_group_plan",
            return_value=fake_plan,
        ):
            with self.assertRaises(Stage2GFunctionOnsetEventError):
                _validate_fold_safety(
                    {
                        "phrase": {
                            "split_group_id": "work",
                            "development_fold": 1,
                        }
                    }
                )

    def test_24_work_family_leakage_fails_closed(self) -> None:
        fake_plan = {
            "group_plan_manifest_sha256": PINNED_GROUP_PLAN_SHA256,
            "groups": [{"split_group_id": "work", "development_fold": 0}],
        }
        with mock.patch(
            "st_harmonic_training.stage2g_function_onset_events.build_stage1e_group_plan",
            return_value=fake_plan,
        ):
            with self.assertRaises(Stage2GFunctionOnsetEventError):
                _validate_fold_safety(
                    {
                        "phrase-a": {
                            "split_group_id": "work",
                            "development_fold": 0,
                        },
                        "phrase-b": {
                            "split_group_id": "work",
                            "development_fold": 1,
                        },
                    }
                )

    def test_25_summary_does_not_serialize_function_tokens(self) -> None:
        summary = build_stage2g_summary(_private_payload())
        rendered = json.dumps(summary, sort_keys=True)
        self.assertNotIn("4T", rendered)
        self.assertNotIn("4D", rendered)
        self.assertNotIn("function_token", rendered)

    def test_26_summary_does_not_serialize_per_record_diagnostics(self) -> None:
        summary = build_stage2g_summary(_private_payload())
        rendered = json.dumps(summary, sort_keys=True)
        self.assertNotIn("Mozart/K279:01:01", rendered)
        self.assertNotIn("phrase_key", rendered)
        self.assertNotIn("carrier_event_id", rendered)

    def test_27_summary_keeps_private_manifest_only(self) -> None:
        payload = _private_payload()
        summary = build_stage2g_summary(payload)
        self.assertEqual(
            summary["private_event_manifest_sha256"],
            payload["private_event_manifest_sha256"],
        )
        self.assertNotIn("events", summary)

    def test_28_repository_output_path_fails_closed(self) -> None:
        with self.assertRaises(Stage2GFunctionOnsetEventHandoffError):
            _assert_external_output_dir(ROOT / "stage2g-private-output")

    def test_29_symlink_output_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target"
            target.mkdir()
            link = root / "link"
            try:
                link.symlink_to(target, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation unavailable")
            with self.assertRaises(Stage2GFunctionOnsetEventHandoffError):
                _assert_external_output_dir(link)

    def test_30_existing_private_artifact_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            (output / "function-onset-events.private.json").write_text(
                "existing", encoding="utf-8"
            )
            with self.assertRaises(FileExistsError):
                _assert_new_outputs(output)

    def test_31_cli_direct_invocation_bootstraps(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/materialize_stage2g_function_onset_events.py"),
                "--help",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Stage 2-G", result.stdout)
        self.assertIn("ONSET_EVENT", result.stdout)

    def test_32_python_3128_runtime_gate_is_preserved(self) -> None:
        self.assertEqual(LOCKED_PYTHON, (3, 12, 8))

    def test_33_deterministic_rerun_produces_same_event_manifest(self) -> None:
        first = _event_rows()
        second = _event_rows()
        self.assertEqual(first, second)
        self.assertEqual(_canonical_sha256(first), _canonical_sha256(second))

    def test_34_model_training_flag_must_remain_false(self) -> None:
        payload = _private_payload()
        payload["model_training_started"] = True
        with self.assertRaises(Stage2GFunctionOnsetEventError):
            build_stage2g_summary(payload)

    def test_35_model_selection_flag_must_remain_false(self) -> None:
        payload = _private_payload()
        payload["model_selection_started"] = True
        with self.assertRaises(Stage2GFunctionOnsetEventError):
            build_stage2g_summary(payload)

    def test_36_event_level_training_authority_must_remain_false(self) -> None:
        payload = _private_payload()
        payload["event_level_training_authorized"] = True
        with self.assertRaises(Stage2GFunctionOnsetEventError):
            build_stage2g_summary(payload)

    def test_37_production_authority_must_remain_false(self) -> None:
        payload = _private_payload()
        payload["production_authority"] = True
        with self.assertRaises(Stage2GFunctionOnsetEventError):
            build_stage2g_summary(payload)

    def test_38_duration_inference_flag_must_remain_false(self) -> None:
        payload = _private_payload()
        payload["duration_inference_used"] = True
        with self.assertRaises(Stage2GFunctionOnsetEventError):
            build_stage2g_summary(payload)

    def test_39_segment_inference_flag_must_remain_false(self) -> None:
        payload = _private_payload()
        payload["segment_boundary_inference_used"] = True
        with self.assertRaises(Stage2GFunctionOnsetEventError):
            build_stage2g_summary(payload)

    def test_40_authority_escalation_tamper_fails_closed(self) -> None:
        contract = build_stage2g_contract()
        contract["production_authority"] = True
        with self.assertRaises(Stage2GFunctionOnsetEventError):
            validate_stage2g_contract(contract)


if __name__ == "__main__":
    unittest.main()
