from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest

from st_harmonic_training.stage2c_contract import (
    CANDIDATE_ALPHAS,
    build_stage2c_contract,
)
from st_harmonic_training.stage2c_specialist_cv import (
    Stage2CSpecialistCVError,
    _evaluate_fold,
    _run_once,
    _run_specialist_candidates,
    canonical_stage2c_summary_json,
    validate_stage2b_private_payload,
)


ROOT = Path(__file__).resolve().parents[1]


def _row(
    phrase: str,
    group: str,
    fold: int,
    label: str,
    *,
    missing_key: bool = False,
    missing_function: bool = False,
) -> dict[str, object]:
    return {
        "phrase_key": phrase,
        "split_group_id": group,
        "development_fold": fold,
        "features": {
            "COMMON": 1,
            f"LABEL_FEATURE::{label}": 8,
        },
        "target_sets": {
            "ROMAN_NUMERAL_SPECIALIST": (label,),
            "KEY_SPECIALIST": () if missing_key else (label,),
            "FUNCTION_SPECIALIST": () if missing_function else (label,),
        },
    }


def _balanced_records() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    index = 0
    for fold in range(3):
        for group_suffix in ("a", "b"):
            group = f"g{fold}{group_suffix}"
            for label in ("LABEL_A", "LABEL_B"):
                rows.append(_row(f"p{index:02d}", group, fold, label))
                index += 1
    return rows


class Stage2CSpecialistCVTests(unittest.TestCase):
    def test_committed_contract_evidence_matches_generator(self) -> None:
        evidence = json.loads(
            (ROOT / "evidence/stage2c_specialist_grouped_cv_contract.v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(evidence, build_stage2c_contract())

    def test_contract_authorizes_only_train_internal_cv(self) -> None:
        contract = build_stage2c_contract()
        self.assertTrue(contract["development_model_fitting_authorized"])
        self.assertFalse(contract["full_train_final_fit_authorized"])
        self.assertFalse(contract["original_validation_target_access"])
        self.assertFalse(contract["calibration_target_access"])
        self.assertFalse(contract["holdout_target_access"])
        self.assertFalse(contract["event_level_training_authorized"])
        self.assertFalse(contract["production_authority"])
        self.assertFalse(contract["calibrated_probability_output"])
        self.assertTrue(contract["deterministic_resolver_remains_authoritative"])

    def test_grouped_cv_can_beat_majority_on_discriminative_features(self) -> None:
        result = _run_specialist_candidates(
            _balanced_records(), "ROMAN_NUMERAL_SPECIALIST"
        )
        self.assertEqual(result["evaluation_record_count"], 12)
        self.assertGreater(
            result["selected_cv_accuracy"], result["majority_baseline_accuracy"]
        )
        self.assertIn(result["selected_alpha"], CANDIDATE_ALPHAS)

    def test_missing_specialist_targets_are_excluded_not_invented(self) -> None:
        rows = _balanced_records()
        rows[0] = _row(
            "p00", "g0a", 0, "LABEL_A", missing_key=True
        )
        result = _run_specialist_candidates(rows, "KEY_SPECIALIST")
        self.assertEqual(result["eligible_record_count"], 11)
        self.assertEqual(result["missing_record_count"], 1)
        self.assertEqual(result["evaluation_record_count"], 11)

    def test_same_work_family_across_fit_and_eval_fails_closed(self) -> None:
        rows = _balanced_records()
        rows[4] = {**rows[4], "split_group_id": "g0a"}
        with self.assertRaisesRegex(Stage2CSpecialistCVError, "work-family leakage"):
            _evaluate_fold(
                rows,
                "ROMAN_NUMERAL_SPECIALIST",
                eval_fold=0,
                alpha=1.0,
            )

    def test_candidate_tie_selects_lowest_frozen_alpha(self) -> None:
        rows = [
            _row(f"p{i}", f"g{i}", i % 3, "ONLY_LABEL") for i in range(6)
        ]
        result = _run_specialist_candidates(rows, "FUNCTION_SPECIALIST")
        self.assertEqual(result["selected_cv_accuracy"], 1.0)
        self.assertEqual(result["selected_alpha"], min(CANDIDATE_ALPHAS))

    def test_cv_summary_is_order_deterministic_and_contains_no_target_values(self) -> None:
        rows = _balanced_records()
        forward = _run_once(rows)
        reverse = _run_once(list(reversed(rows)))
        self.assertEqual(forward, reverse)
        encoded = json.dumps(forward, sort_keys=True)
        self.assertNotIn("LABEL_A", encoded)
        self.assertNotIn("LABEL_B", encoded)

    def test_stage2b_pin_mismatch_fails_before_any_cv(self) -> None:
        with self.assertRaisesRegex(Stage2CSpecialistCVError, "input pin mismatch"):
            validate_stage2b_private_payload(
                {
                    "schema_version": "st-stage2b-specialist-train-materialization-v1",
                    "source_corpus": "WRONG",
                }
            )

    def test_summary_rejects_original_validation_access(self) -> None:
        summary = {
            "schema_version": "st-stage2c-specialist-grouped-cv-summary-v1",
            "deterministic_rerun_match": True,
            "full_train_final_fit_started": False,
            "original_validation_target_access": True,
            "calibration_target_access": False,
            "holdout_target_access": False,
            "event_level_training_authorized": False,
            "production_authority": False,
            "calibrated_probability_output": False,
            "deterministic_resolver_remains_authoritative": True,
        }
        with self.assertRaisesRegex(Stage2CSpecialistCVError, "authority violation"):
            canonical_stage2c_summary_json(summary)

    def test_direct_cli_help_bootstraps_repository_imports(self) -> None:
        completed = subprocess.run(
            [sys.executable, "scripts/run_stage2c_specialist_cv.py", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("TRAIN-only 3-fold grouped CV", completed.stdout)


if __name__ == "__main__":
    unittest.main()
