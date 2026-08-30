from __future__ import annotations

import json
from pathlib import Path
import unittest
from unittest import mock

from st_harmonic_training.stage2j_function_event_index_cv import (
    AUTHORIZED_EVENT_FEATURES,
    FEATURE_PREFIX,
    Stage2JFunctionEventIndexCVError,
    _index_feature_vector,
    build_stage2j_contract,
    run_stage2j_grouped_cv,
    validate_stage2j_contract,
)

ROOT = Path(__file__).resolve().parents[1]


def _rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for fold in range(3):
        for index in range(6):
            target = "T" if index < 3 else "D"
            phrase_features = {"phrase": 1}
            index_features = {
                "phrase": 1,
                f"{FEATURE_PREFIX}function={index}": 1,
                f"{FEATURE_PREFIX}harmonic={index}": 1,
            }
            rows.append(
                {
                    "event_id": f"e-{fold}-{index}",
                    "split_group_id": f"work-{fold}",
                    "development_fold": fold,
                    "target": target,
                    "phrase_features": phrase_features,
                    "index_features": index_features,
                }
            )
    return rows


class Stage2JFunctionEventIndexCVTests(unittest.TestCase):
    def test_committed_contract_matches_builder(self) -> None:
        committed = json.loads(
            (ROOT / "evidence/stage2j_function_event_index_cv_contract.v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(committed, build_stage2j_contract())
        validate_stage2j_contract(committed)

    def test_only_stage2i_approved_event_fields_are_authorized(self) -> None:
        self.assertEqual(
            AUTHORIZED_EVENT_FEATURES,
            ("FUNCTION_EVENT_INDEX", "CARRIER_HARMONIC_EVENT_INDEX"),
        )
        contract = build_stage2j_contract()
        self.assertFalse(contract["source_provenance_as_model_feature_authorized"])
        self.assertFalse(contract["carrier_source_order_as_model_feature_authorized"])
        self.assertFalse(contract["index_gap_feature_authorized"])

    def test_non_train_and_production_boundaries_stay_closed(self) -> None:
        contract = build_stage2j_contract()
        for field in (
            "original_validation_target_access",
            "calibration_target_access",
            "holdout_target_access",
            "full_train_final_fit_started",
            "production_authority",
            "explicit_onset_feature_authorized",
            "duration_feature_authorized",
            "segment_boundary_feature_authorized",
            "local_harmonic_label_feature_authorized",
            "local_score_context_feature_authorized",
            "function_token_rewrite_authorized",
        ):
            self.assertFalse(contract[field])
        self.assertTrue(contract["cv_model_fit_authorized"])
        self.assertTrue(contract["deterministic_resolver_remains_authoritative"])

    def test_index_encoding_is_exact_categorical_one_hot(self) -> None:
        features = _index_feature_vector({"pitch:C": 2}, 3, 5)
        self.assertEqual(features["pitch:C"], 2)
        self.assertEqual(features[f"{FEATURE_PREFIX}function=3"], 1)
        self.assertEqual(features[f"{FEATURE_PREFIX}harmonic=5"], 1)
        self.assertEqual(len(features), 3)

    def test_index_namespace_collision_fails_closed(self) -> None:
        with self.assertRaises(Stage2JFunctionEventIndexCVError):
            _index_feature_vector({f"{FEATURE_PREFIX}function=0": 1}, 0, 0)

    def test_grouped_cv_reports_phrase_only_and_index_augmented(self) -> None:
        with mock.patch(
            "st_harmonic_training.stage2j_function_event_index_cv._join_rows",
            return_value=_rows(),
        ):
            summary = run_stage2j_grouped_cv({}, {})
        self.assertEqual(summary["materialized_event_count"], 18)
        self.assertIn("phrase_only_reference", summary)
        self.assertIn("index_augmented", summary)
        self.assertGreater(
            summary["index_augmented"]["selected_pooled_accuracy"],
            summary["phrase_only_reference"]["selected_pooled_accuracy"],
        )
        self.assertFalse(summary["calibrated_probability_output"])
        self.assertFalse(summary["production_authority"])

    def test_work_family_cross_fold_leakage_fails_closed(self) -> None:
        rows = _rows()
        rows[6]["split_group_id"] = "work-0"
        with mock.patch(
            "st_harmonic_training.stage2j_function_event_index_cv._join_rows",
            return_value=rows,
        ):
            with self.assertRaises(Stage2JFunctionEventIndexCVError):
                run_stage2j_grouped_cv({}, {})

    def test_summary_is_aggregate_only(self) -> None:
        with mock.patch(
            "st_harmonic_training.stage2j_function_event_index_cv._join_rows",
            return_value=_rows(),
        ):
            summary = run_stage2j_grouped_cv({}, {})
        rendered = json.dumps(summary, sort_keys=True)
        for private_value in ("e-0-0", "function_token", "phrase_key", "carrier_event_id"):
            self.assertNotIn(private_value, rendered)

    def test_contract_tamper_fails_closed(self) -> None:
        contract = build_stage2j_contract()
        contract["holdout_target_access"] = True
        with self.assertRaises(Stage2JFunctionEventIndexCVError):
            validate_stage2j_contract(contract)


if __name__ == "__main__":
    unittest.main()
