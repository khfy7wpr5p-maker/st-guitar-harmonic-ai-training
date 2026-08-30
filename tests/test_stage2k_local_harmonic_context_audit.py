from __future__ import annotations

import json
from pathlib import Path
import unittest

from st_harmonic_training.stage2k_local_harmonic_context_audit import (
    CONTEXT_SOURCE,
    Stage2KLocalHarmonicContextAuditError,
    _audit_path_context,
    _parse_harmonic_tokens,
    build_stage2k_contract,
    validate_stage2k_contract,
)

ROOT = Path(__file__).resolve().parents[1]


class Stage2KLocalHarmonicContextAuditTests(unittest.TestCase):
    def test_committed_contract_matches_builder(self) -> None:
        committed = json.loads(
            (ROOT / "evidence/stage2k_local_harmonic_context_feasibility_audit_contract.v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(committed, build_stage2k_contract())
        validate_stage2k_contract(committed)

    def test_contract_is_audit_only(self) -> None:
        contract = build_stage2k_contract()
        self.assertEqual(contract["context_source"], CONTEXT_SOURCE)
        for field in (
            "feature_materialization_authorized",
            "model_training_started",
            "model_selection_started",
            "full_train_final_fit_started",
            "inference_time_feature_availability_established",
            "joined_harmonic_labels_authoritative",
            "function_token_rewrite_authorized",
            "duration_inference_authorized",
            "segment_boundary_inference_authorized",
            "non_train_annotation_bodies_materialized",
            "original_validation_target_access",
            "calibration_target_access",
            "holdout_target_access",
            "production_authority",
        ):
            self.assertFalse(contract[field])
        self.assertTrue(contract["deterministic_resolver_remains_authoritative"])

    def test_parse_harmonic_tokens_ignores_non_data_rows(self) -> None:
        text = "\n".join(
            [
                "**harm\t**function",
                "*M4/4\t*M4/4",
                "I\tT",
                ".\t.",
                "V\tD",
                "=2\t=2",
                "ii6\tS",
                "*-\t*-",
            ]
        )
        self.assertEqual(_parse_harmonic_tokens(text), ["I", "V", "ii6"])

    def test_parse_requires_single_harmonic_spine(self) -> None:
        with self.assertRaises(Stage2KLocalHarmonicContextAuditError):
            _parse_harmonic_tokens("**foo\t**function\nx\tT")

    def test_path_context_counts_previous_current_next(self) -> None:
        events = [
            {"function_event_index": 0, "carrier_harmonic_event_index": 0},
            {"function_event_index": 1, "carrier_harmonic_event_index": 2},
            {"function_event_index": 2, "carrier_harmonic_event_index": 3},
        ]
        result = _audit_path_context(events, ["I", "IV", "V", "I6"])
        self.assertEqual(result["current_count"], 3)
        self.assertEqual(result["previous_count"], 2)
        self.assertEqual(result["next_count"], 2)
        self.assertEqual(result["one_sided_or_better_count"], 3)
        self.assertEqual(result["full_triplet_count"], 1)
        self.assertEqual(result["current_tokens"], ["I", "V", "I6"])

    def test_out_of_range_carrier_fails_closed(self) -> None:
        events = [{"function_event_index": 0, "carrier_harmonic_event_index": 2}]
        with self.assertRaises(Stage2KLocalHarmonicContextAuditError):
            _audit_path_context(events, ["I"])

    def test_negative_carrier_fails_closed(self) -> None:
        events = [{"function_event_index": 0, "carrier_harmonic_event_index": -1}]
        with self.assertRaises(Stage2KLocalHarmonicContextAuditError):
            _audit_path_context(events, ["I"])

    def test_contract_tamper_fails_closed(self) -> None:
        contract = build_stage2k_contract()
        contract["feature_materialization_authorized"] = True
        with self.assertRaises(Stage2KLocalHarmonicContextAuditError):
            validate_stage2k_contract(contract)


if __name__ == "__main__":
    unittest.main()
