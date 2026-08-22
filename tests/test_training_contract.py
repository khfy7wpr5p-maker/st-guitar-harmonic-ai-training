from __future__ import annotations

import copy
import unittest

from st_harmonic_training.training_contract import (
    TrainingContractError,
    build_stage1a_training_contract,
    canonical_training_contract_json,
    validate_stage1a_training_contract,
)
from st_harmonic_training.tavern_structure import PINNED_TAVERN_REVISION


class TrainingContractTests(unittest.TestCase):
    def readiness(self, *, status="HOLD", raw=False, normalized=False):
        blockers = [] if status == "PASS" else ["RAW_LABEL_REALIZATION_PENDING", "DETERMINISTIC_NORMALIZATION_PENDING"]
        return {
            "schema_version":"st-tavern-final-readiness-audit-v1",
            "source_corpus":"TAVERN_REVIEWED_694","source_revision":PINNED_TAVERN_REVISION,
            "eligible_record_count":694,"gold_tier_counts":{"GOLD_EXPERT":641,"GOLD_VARIANT":53},
            "split_seed":"st-tavern-split-v1:12",
            "split_distribution":{"CALIBRATION":41,"HOLDOUT":41,"TRAIN":487,"VALIDATION":125},
            "leakage_gate":"PASS","cross_corpus_lineage_bound":True,
            "teacher_gold_present_in_calibration":True,"teacher_gold_present_in_holdout":True,
            "raw_label_realization_complete":raw,"normalization_complete":normalized,
            "blockers":blockers,"gate_status":status,"training_authorized":status == "PASS",
        }

    def test_current_hold_freezes_contract_without_starting_training(self):
        contract = build_stage1a_training_contract(self.readiness())
        self.assertEqual(contract["contract_status"], "FROZEN_PRETRAINING_CONTRACT")
        self.assertFalse(contract["training_start_guard"]["pass"])
        self.assertIn("RAW_LABEL_REALIZATION_PENDING", contract["training_start_guard"]["blockers"])
        self.assertIn("DETERMINISTIC_NORMALIZATION_PENDING", contract["training_start_guard"]["blockers"])
        self.assertIn("PROMOTION_THRESHOLDS_PENDING_BASELINE", contract["training_start_guard"]["blockers"])
        self.assertFalse(contract["model_training_started"])
        self.assertFalse(contract["training_authorized"])

    def test_even_future_readiness_pass_does_not_auto_start_training(self):
        contract = build_stage1a_training_contract(self.readiness(status="PASS", raw=True, normalized=True))
        self.assertEqual(contract["training_start_guard"]["stage0u_gate_status"], "PASS")
        self.assertEqual(contract["training_start_guard"]["blockers"], ["PROMOTION_THRESHOLDS_PENDING_BASELINE"])
        self.assertFalse(contract["training_start_guard"]["pass"])
        self.assertFalse(contract["training_authorized"])

    def test_variant_collapse_fails_closed(self):
        contract = build_stage1a_training_contract(self.readiness())
        contract["target_contract"]["arbitrary_variant_collapse_allowed"] = True
        with self.assertRaises(TrainingContractError): validate_stage1a_training_contract(contract)

    def test_holdout_training_access_fails_closed(self):
        contract = build_stage1a_training_contract(self.readiness())
        contract["partition_contract"]["holdout_access_during_training"] = True
        with self.assertRaises(TrainingContractError): validate_stage1a_training_contract(contract)

    def test_holdout_model_selection_access_fails_closed(self):
        contract = build_stage1a_training_contract(self.readiness())
        contract["partition_contract"]["holdout_access_during_model_selection"] = True
        with self.assertRaises(TrainingContractError): validate_stage1a_training_contract(contract)

    def test_augmentation_outside_train_fails_closed(self):
        contract = build_stage1a_training_contract(self.readiness())
        contract["partition_contract"]["augmentation_scope"] = "ALL_PARTITIONS"
        with self.assertRaises(TrainingContractError): validate_stage1a_training_contract(contract)

    def test_uncalibrated_probability_claim_fails_closed(self):
        contract = build_stage1a_training_contract(self.readiness())
        contract["confidence_contract"]["raw_model_score_is_probability"] = True
        with self.assertRaises(TrainingContractError): validate_stage1a_training_contract(contract)

    def test_checkpoint_in_git_policy_cannot_be_disabled(self):
        contract = build_stage1a_training_contract(self.readiness())
        contract["artifact_security_contract"]["checkpoints_in_git_forbidden"] = False
        with self.assertRaises(TrainingContractError): validate_stage1a_training_contract(contract)

    def test_training_authority_escalation_fails_closed(self):
        contract = build_stage1a_training_contract(self.readiness())
        contract["training_authorized"] = True
        with self.assertRaises(TrainingContractError): validate_stage1a_training_contract(contract)

    def test_readiness_authority_inconsistency_fails_closed(self):
        readiness = self.readiness(); readiness["training_authorized"] = True
        with self.assertRaises(TrainingContractError): build_stage1a_training_contract(readiness)

    def test_canonical_contract_is_deterministic(self):
        left = build_stage1a_training_contract(self.readiness())
        right = build_stage1a_training_contract(copy.deepcopy(self.readiness()))
        self.assertEqual(canonical_training_contract_json(left), canonical_training_contract_json(right))


if __name__ == "__main__": unittest.main()
