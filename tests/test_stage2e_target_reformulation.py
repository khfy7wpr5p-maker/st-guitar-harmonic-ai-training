from __future__ import annotations

import json
from pathlib import Path
import unittest

from st_harmonic_training.stage2e_target_reformulation import (
    Stage2ETargetReformulationError,
    build_stage2d_private_receipt,
    build_stage2e_contract,
    validate_stage2d_private_receipt,
    validate_stage2e_contract,
)


ROOT = Path(__file__).resolve().parents[1]


class Stage2ETargetReformulationTests(unittest.TestCase):
    def test_committed_stage2d_receipt_matches_bounded_builder(self) -> None:
        committed = json.loads(
            (ROOT / "evidence/stage2d_private_learnability_receipt.v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(committed, build_stage2d_private_receipt())
        validate_stage2d_private_receipt(committed)

    def test_committed_stage2e_contract_matches_builder(self) -> None:
        committed = json.loads(
            (ROOT / "evidence/stage2e_target_reformulation_contract.v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(committed, build_stage2e_contract())
        validate_stage2e_contract(committed)

    def test_key_preserves_scalar_target_only(self) -> None:
        contract = build_stage2e_contract()
        key = contract["specialists"]["KEY_SPECIALIST"]
        self.assertEqual(key["target_decision"], "PRESERVE_SCALAR_TARGET")
        self.assertEqual(key["next_target_shape"], "SCALAR_CLASS")
        self.assertEqual(
            key["next_prerequisite"],
            "SEPARATE_TRAIN_ONLY_MODEL_FEATURE_GATE_REQUIRED",
        )

    def test_sequence_specialists_retire_whole_phrase_classification(self) -> None:
        contract = build_stage2e_contract()
        for specialist_id in ("FUNCTION_SPECIALIST", "ROMAN_NUMERAL_SPECIALIST"):
            item = contract["specialists"][specialist_id]
            self.assertEqual(
                item["target_decision"],
                "RETIRE_WHOLE_PHRASE_CLASSIFICATION_TARGET",
            )
            self.assertNotEqual(item["next_target_shape"], item["current_target_shape"])

    def test_function_alignment_must_be_proven_before_materialization(self) -> None:
        contract = build_stage2e_contract()
        function = contract["specialists"]["FUNCTION_SPECIALIST"]
        self.assertEqual(contract["function_alignment_scope"], "NOT_YET_PROVEN")
        self.assertEqual(
            function["next_prerequisite"],
            "FUNCTION_EVENT_CARRIER_ALIGNMENT_AUDIT_REQUIRED",
        )
        self.assertFalse(contract["event_target_materialization_authorized"])
        self.assertFalse(contract["event_level_training_authorized"])

    def test_roman_event_path_stays_non_authoritative(self) -> None:
        contract = build_stage2e_contract()
        roman = contract["specialists"]["ROMAN_NUMERAL_SPECIALIST"]
        self.assertEqual(
            contract["roman_alignment_scope"],
            "STAGE1D_CANDIDATES_ONLY_NOT_AUTHORITY",
        )
        self.assertEqual(
            roman["next_prerequisite"],
            "STAGE1E_PRIVATE_TRAIN_EVENT_MATERIALIZATION_AND_STAGE1F_CONTRACT_REQUIRED",
        )
        self.assertFalse(contract["stage1d_quarantine_reuse_authorized"])

    def test_stage2e_opens_no_model_or_partition_authority(self) -> None:
        contract = build_stage2e_contract()
        for field in (
            "model_fitting_authorized",
            "model_selection_authorized",
            "full_train_final_fit_authorized",
            "event_target_materialization_authorized",
            "event_level_training_authorized",
            "original_validation_target_access",
            "calibration_target_access",
            "holdout_target_access",
            "production_authority",
            "calibrated_probability_output",
        ):
            self.assertFalse(contract[field], field)
        self.assertTrue(contract["deterministic_resolver_remains_authoritative"])

    def test_receipt_is_privacy_bounded_and_does_not_invent_file_hash(self) -> None:
        receipt = build_stage2d_private_receipt()
        self.assertFalse(receipt["exact_summary_file_sha256_bound"])
        self.assertFalse(receipt["target_values_serialized"])
        serialized = json.dumps(receipt, sort_keys=True)
        self.assertNotIn("phrase_key", serialized)
        self.assertNotIn("source_targets", serialized)
        self.assertNotIn("effective_targets", serialized)
        self.assertNotIn("features", serialized)

    def test_authority_escalation_tamper_fails_closed(self) -> None:
        tampered = build_stage2e_contract()
        tampered["event_target_materialization_authorized"] = True
        with self.assertRaises(Stage2ETargetReformulationError):
            validate_stage2e_contract(tampered)


if __name__ == "__main__":
    unittest.main()
