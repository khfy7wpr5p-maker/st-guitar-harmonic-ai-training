from __future__ import annotations

import json
from pathlib import Path
import unittest
from unittest import mock

from st_harmonic_training.stage2i_function_event_feature_audit import (
    Stage2IFunctionEventFeatureAuditError,
    build_stage2i_contract,
    run_stage2i_audit,
    validate_stage2i_contract,
)

ROOT = Path(__file__).resolve().parents[1]


def _events() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for fold in range(3):
        for source in ("A", "B"):
            for index, harmonic_index in enumerate((0, 2, 3)):
                rows.append(
                    {
                        "phrase_key": f"p-{fold}",
                        "source": source,
                        "source_annotation_sha256": "a" * 64,
                        "split_group_id": f"work-{fold}",
                        "development_fold": fold,
                        "carrier_event_id": f"e-{fold}-{source}-{index}",
                        "carrier_harmonic_event_index": harmonic_index,
                        "carrier_source_order_index": 10 + index * 2,
                        "function_event_index": index,
                        "function_token": "T" if index < 2 else "D",
                        "target_shape": "ONSET_EVENT",
                    }
                )
    return rows


class Stage2IFunctionEventFeatureAuditTests(unittest.TestCase):
    def test_committed_contract_matches_builder(self) -> None:
        committed = json.loads(
            (ROOT / "evidence/stage2i_function_event_feature_alignment_audit_contract.v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(committed, build_stage2i_contract())
        validate_stage2i_contract(committed)

    def test_contract_is_audit_only(self) -> None:
        contract = build_stage2i_contract()
        self.assertEqual(contract["eligible_original_partition"], "TRAIN")
        self.assertFalse(contract["feature_materialization_authorized"])
        self.assertFalse(contract["model_training_started"])
        self.assertFalse(contract["model_selection_started"])
        self.assertFalse(contract["production_authority"])
        self.assertTrue(contract["deterministic_resolver_remains_authoritative"])

    def test_contract_marks_unavailable_semantics_explicitly(self) -> None:
        contract = build_stage2i_contract()
        self.assertFalse(contract["explicit_onset_value_available_in_stage2g_payload"])
        self.assertFalse(contract["duration_available_in_stage2g_payload"])
        self.assertFalse(contract["segment_boundary_available_in_stage2g_payload"])
        self.assertFalse(contract["local_harmonic_label_context_available_in_stage2g_payload"])
        self.assertFalse(contract["local_score_context_available_in_stage2g_payload"])

    def test_contract_tamper_fails_closed(self) -> None:
        contract = build_stage2i_contract()
        contract["feature_materialization_authorized"] = True
        with self.assertRaises(Stage2IFunctionEventFeatureAuditError):
            validate_stage2i_contract(contract)

    def test_audit_reports_existing_order_fields_without_private_rows(self) -> None:
        with mock.patch(
            "st_harmonic_training.stage2i_function_event_feature_audit._validate_stage2g_private_payload",
            return_value=_events(),
        ), mock.patch(
            "st_harmonic_training.stage2i_function_event_feature_audit.EXPECTED_STAGE2G_EVENT_COUNT",
            len(_events()),
        ):
            summary = run_stage2i_audit({})
        rendered = json.dumps(summary, sort_keys=True)
        self.assertEqual(summary["materialized_event_count"], 18)
        self.assertEqual(summary["source_path_count"], 6)
        self.assertEqual(summary["phrase_count"], 3)
        self.assertEqual(summary["harmonic_gap_event_count"], 6)
        self.assertEqual(summary["harmonic_function_index_divergence_count"], 12)
        self.assertEqual(summary["audit_supported_feature_candidates"], [
            "FUNCTION_EVENT_INDEX",
            "CARRIER_HARMONIC_EVENT_INDEX",
        ])
        self.assertNotIn('"phrase_key"', rendered)
        self.assertNotIn('"function_token"', rendered)
        self.assertNotIn('"carrier_event_id"', rendered)

    def test_nonconsecutive_function_index_fails_closed(self) -> None:
        events = _events()
        events[1]["function_event_index"] = 3
        with mock.patch(
            "st_harmonic_training.stage2i_function_event_feature_audit._validate_stage2g_private_payload",
            return_value=events,
        ), mock.patch(
            "st_harmonic_training.stage2i_function_event_feature_audit.EXPECTED_STAGE2G_EVENT_COUNT",
            len(events),
        ):
            with self.assertRaises(Stage2IFunctionEventFeatureAuditError):
                run_stage2i_audit({})

    def test_nonmonotonic_harmonic_index_fails_closed(self) -> None:
        events = _events()
        events[1]["carrier_harmonic_event_index"] = 0
        with mock.patch(
            "st_harmonic_training.stage2i_function_event_feature_audit._validate_stage2g_private_payload",
            return_value=events,
        ), mock.patch(
            "st_harmonic_training.stage2i_function_event_feature_audit.EXPECTED_STAGE2G_EVENT_COUNT",
            len(events),
        ):
            with self.assertRaises(Stage2IFunctionEventFeatureAuditError):
                run_stage2i_audit({})

    def test_source_provenance_is_not_authorized_as_model_feature(self) -> None:
        self.assertFalse(build_stage2i_contract()["source_provenance_as_model_feature_authorized"])

    def test_non_train_access_remains_closed(self) -> None:
        contract = build_stage2i_contract()
        self.assertFalse(contract["original_validation_target_access"])
        self.assertFalse(contract["calibration_target_access"])
        self.assertFalse(contract["holdout_target_access"])


if __name__ == "__main__":
    unittest.main()
