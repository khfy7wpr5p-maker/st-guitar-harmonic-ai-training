from __future__ import annotations

import json
from pathlib import Path
import unittest
from unittest import mock

from st_harmonic_training.stage2h_function_event_cv import (
    EXPECTED_STAGE2G_EVENT_COUNT,
    EXPECTED_STAGE2G_MATERIALIZABLE_SOURCE_PATH_COUNT,
    EXPECTED_STAGE2G_PRIVATE_EVENT_MANIFEST_SHA256,
    FORBIDDEN_SHAREABLE_KEYS,
    SCORE_SEMANTICS,
    Stage2HFunctionEventCVError,
    _contains_forbidden_shareable_key,
    _fit_nb,
    _predict_nb,
    build_stage2h_contract,
    run_stage2h_grouped_cv,
    validate_stage2h_contract,
)

ROOT = Path(__file__).resolve().parents[1]


def _rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for fold in range(3):
        for index in range(4):
            target = "T" if index < 3 else "D"
            rows.append(
                {
                    "event_id": f"e-{fold}-{index}",
                    "phrase_key": f"p-{fold}-{index}",
                    "split_group_id": f"work-{fold}",
                    "development_fold": fold,
                    "source": "A",
                    "features": {"x": 4 if target == "T" else 1, "y": 1 if target == "T" else 4},
                    "target": target,
                }
            )
    return rows


class Stage2HFunctionEventCVTests(unittest.TestCase):
    def test_committed_contract_matches_builder(self) -> None:
        committed = json.loads(
            (ROOT / "evidence/stage2h_function_event_grouped_cv_contract.v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(committed, build_stage2h_contract())
        validate_stage2h_contract(committed)

    def test_contract_is_train_only_and_grouped_by_work_family(self) -> None:
        contract = build_stage2h_contract()
        self.assertEqual(contract["eligible_original_partition"], "TRAIN")
        self.assertEqual(contract["grouping_unit"], "SPLIT_GROUP_ID_WORK_FAMILY")
        self.assertEqual(contract["fold_source"], "STAGE1E_DEVELOPMENT_FOLD")
        self.assertFalse(contract["event_random_split_authorized"])
        self.assertFalse(contract["phrase_random_split_authorized"])
        self.assertFalse(contract["cross_work_family_leakage_authorized"])

    def test_stage2g_private_event_pin_is_frozen(self) -> None:
        self.assertEqual(EXPECTED_STAGE2G_EVENT_COUNT, 1854)
        self.assertEqual(EXPECTED_STAGE2G_MATERIALIZABLE_SOURCE_PATH_COUNT, 363)
        self.assertEqual(
            EXPECTED_STAGE2G_PRIVATE_EVENT_MANIFEST_SHA256,
            "d7bbd514ec85b87aee423cae9dce39c74e634ab2f1040fed82af0e25105f255d",
        )

    def test_contract_keeps_non_train_and_production_authority_closed(self) -> None:
        contract = build_stage2h_contract()
        for field in (
            "original_validation_target_access",
            "calibration_target_access",
            "holdout_target_access",
            "production_authority",
            "full_train_final_fit_started",
            "duration_inference_authorized",
            "segment_boundary_inference_authorized",
            "function_token_rewrite_authorized",
            "joined_harmonic_labels_authoritative",
        ):
            self.assertFalse(contract[field])
        self.assertTrue(contract["deterministic_resolver_remains_authoritative"])
        self.assertTrue(contract["cv_model_fit_authorized"])

    def test_contract_tamper_fails_closed(self) -> None:
        contract = build_stage2h_contract()
        contract["holdout_target_access"] = True
        with self.assertRaises(Stage2HFunctionEventCVError):
            validate_stage2h_contract(contract)

    def test_nb_prediction_uses_model_score_not_probability(self) -> None:
        rows = _rows()[:4]
        model = _fit_nb(rows, 1.0)
        self.assertEqual(_predict_nb(model, {"x": 5, "y": 1}), "T")
        self.assertEqual(SCORE_SEMANTICS, "MODEL_SCORE_NOT_PROBABILITY")

    def test_grouped_cv_summary_is_aggregate_only(self) -> None:
        with mock.patch(
            "st_harmonic_training.stage2h_function_event_cv._join_event_rows",
            return_value=_rows(),
        ):
            summary = run_stage2h_grouped_cv({}, {})
        rendered = json.dumps(summary, sort_keys=True)
        self.assertEqual(summary["materialized_event_count"], 12)
        self.assertEqual(summary["fold_event_distribution"], {"0": 4, "1": 4, "2": 4})
        self.assertFalse(summary["original_validation_target_access"])
        self.assertFalse(summary["calibration_target_access"])
        self.assertFalse(summary["holdout_target_access"])
        self.assertFalse(summary["production_authority"])
        self.assertTrue(summary["cv_model_fit_performed"])
        self.assertFalse(summary["function_token_rewrite_used"])
        self.assertFalse(_contains_forbidden_shareable_key(summary))
        self.assertTrue(FORBIDDEN_SHAREABLE_KEYS.isdisjoint(summary.keys()))
        self.assertNotIn("e-0-0", rendered)
        self.assertNotIn("p-0-0", rendered)

    def test_exact_private_keys_are_detected_without_false_prefix_match(self) -> None:
        self.assertTrue(_contains_forbidden_shareable_key({"function_token": "T"}))
        self.assertTrue(_contains_forbidden_shareable_key({"nested": [{"phrase_key": "p"}]}))
        self.assertFalse(_contains_forbidden_shareable_key({"function_token_rewrite_used": False}))

    def test_work_family_cross_fold_leakage_fails_closed(self) -> None:
        rows = _rows()
        rows[4]["split_group_id"] = "work-0"
        with mock.patch(
            "st_harmonic_training.stage2h_function_event_cv._join_event_rows",
            return_value=rows,
        ):
            with self.assertRaises(Stage2HFunctionEventCVError):
                run_stage2h_grouped_cv({}, {})

    def test_summary_never_claims_calibrated_probability(self) -> None:
        with mock.patch(
            "st_harmonic_training.stage2h_function_event_cv._join_event_rows",
            return_value=_rows(),
        ):
            summary = run_stage2h_grouped_cv({}, {})
        self.assertFalse(summary["calibrated_probability_output"])
        self.assertEqual(summary["score_semantics"], SCORE_SEMANTICS)


if __name__ == "__main__":
    unittest.main()
