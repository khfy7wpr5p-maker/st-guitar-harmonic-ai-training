from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest

from st_harmonic_training.stage2f_function_alignment import (
    build_stage2f_contract,
    classify_function_source_path,
    parse_function_carrier_rows,
    validate_stage2f_contract,
)


ROOT = Path(__file__).resolve().parents[1]


def _joined(*harmonic_tokens: str) -> str:
    rows = ["**kern\t**harm"]
    for index, token in enumerate(harmonic_tokens):
        rows.append(f"4c\t{token}")
    rows.append("*-\t*-")
    return "\n".join(rows) + "\n"


class Stage2FFunctionAlignmentTests(unittest.TestCase):
    def test_committed_contract_evidence_matches_builder(self) -> None:
        committed = json.loads(
            (ROOT / "evidence/stage2f_function_alignment_contract.v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(committed, build_stage2f_contract())
        validate_stage2f_contract(committed)

    def test_contract_opens_no_training_or_partition_authority(self) -> None:
        contract = build_stage2f_contract()
        for field in (
            "target_shape_decision_authorized",
            "event_target_materialization_authorized",
            "model_fitting_authorized",
            "model_selection_authorized",
            "full_train_final_fit_authorized",
            "event_level_training_authorized",
            "original_validation_target_access",
            "calibration_target_access",
            "holdout_target_access",
            "stage1d_quarantine_reuse_authorized",
            "production_authority",
        ):
            self.assertIs(contract[field], False)
        self.assertIs(contract["joined_harmonic_labels_authoritative"], False)
        self.assertIs(contract["deterministic_resolver_remains_authoritative"], True)

    def test_function_rows_map_to_harmonic_onsets_without_serializing_targets(self) -> None:
        encoder = (
            "**harm\t**function\n"
            "*C:\t*\n"
            "4I\t4T\n"
            "4V\t4D\n"
            "*-\t*-\n"
        )
        parsed = parse_function_carrier_rows(encoder)
        self.assertEqual(parsed["function_event_count"], 2)
        self.assertEqual(parsed["function_on_harmonic_event_count"], 2)
        self.assertEqual(parsed["function_without_harmonic_event_count"], 0)
        diagnostic = classify_function_source_path(encoder, _joined("4I", "4V"))
        self.assertEqual(diagnostic["status"], "FUNCTION_ONSET_CARRIER_CANDIDATE")
        self.assertIs(diagnostic["duration_exact_single_event_candidate"], True)
        rendered = json.dumps(diagnostic, sort_keys=True)
        self.assertNotIn('"T"', rendered)
        self.assertNotIn('"D"', rendered)

    def test_duration_mismatch_does_not_destroy_valid_onset_carrier(self) -> None:
        encoder = (
            "**harm\t**function\n"
            "4I\t2T\n"
            "4V\t4D\n"
            "*-\t*-\n"
        )
        diagnostic = classify_function_source_path(encoder, _joined("4I", "4V"))
        self.assertEqual(diagnostic["status"], "FUNCTION_ONSET_CARRIER_CANDIDATE")
        self.assertIs(diagnostic["duration_exact_single_event_candidate"], False)
        self.assertEqual(diagnostic["function_harmonic_reciprocal_mismatch_count"], 1)

    def test_function_without_harmonic_row_carrier_is_quarantined(self) -> None:
        encoder = (
            "**harm\t**function\n"
            "4I\t4T\n"
            ".\t4D\n"
            "4V\t.\n"
            "*-\t*-\n"
        )
        diagnostic = classify_function_source_path(encoder, _joined("4I", "4V"))
        self.assertEqual(diagnostic["status"], "QUARANTINE")
        self.assertIn(
            "FUNCTION_EVENT_WITHOUT_HARMONIC_ROW_CARRIER",
            diagnostic["quarantine_reasons"],
        )

    def test_encoder_joined_reciprocal_mismatch_is_quarantined(self) -> None:
        encoder = (
            "**harm\t**function\n"
            "4I\t4T\n"
            "4V\t4D\n"
            "*-\t*-\n"
        )
        diagnostic = classify_function_source_path(encoder, _joined("4I", "2V"))
        self.assertEqual(diagnostic["status"], "QUARANTINE")
        self.assertIn(
            "ENCODER_JOINED_RECIPROCAL_SEQUENCE_MISMATCH",
            diagnostic["quarantine_reasons"],
        )

    def test_missing_function_spine_stays_ineligible(self) -> None:
        encoder = "**harm\n4I\n4V\n*-\n"
        diagnostic = classify_function_source_path(encoder, _joined("4I", "4V"))
        self.assertEqual(diagnostic["status"], "FUNCTION_SPINE_MISSING")
        self.assertEqual(diagnostic["function_event_count"], 0)

    def test_authority_escalation_tamper_fails_closed(self) -> None:
        tampered = build_stage2f_contract()
        tampered["event_target_materialization_authorized"] = True
        with self.assertRaises(Exception):
            validate_stage2f_contract(tampered)

    def test_direct_cli_help_bootstraps_repository_imports(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/run_stage2f_function_alignment_audit.py"),
                "--help",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Stage 2-F", result.stdout)


if __name__ == "__main__":
    unittest.main()
