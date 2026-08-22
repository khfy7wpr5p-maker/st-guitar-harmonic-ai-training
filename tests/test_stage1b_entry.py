from __future__ import annotations

import copy
import unittest

from st_harmonic_training.baseline_thresholds import THRESHOLD_SCHEMA
from st_harmonic_training.stage1b_entry import (
    ENTRY_SCHEMA,
    EXPECTED_THRESHOLDS,
    Stage1BEntryError,
    build_stage1b_entry_audit,
)
from st_harmonic_training.tavern_readiness_completion import COMPLETION_SCHEMA
from st_harmonic_training.tavern_structure import PINNED_TAVERN_REVISION


class Stage1BEntryTests(unittest.TestCase):
    def readiness(self):
        return {
            "schema_version": COMPLETION_SCHEMA,
            "source_corpus": "TAVERN_REVIEWED_694",
            "source_revision": PINNED_TAVERN_REVISION,
            "dataset_readiness_gate": "PASS",
            "training_payload_ready": True,
            "leakage_gate": "PASS",
            "training_authorized": False,
        }

    def thresholds(self):
        return {
            "schema_version": THRESHOLD_SCHEMA,
            "source_corpus": "TAVERN_REVIEWED_694",
            "source_revision": PINNED_TAVERN_REVISION,
            "promotion_threshold_status": "FROZEN",
            "promotion_scope": "OFFLINE_SHADOW_ONLY",
            "validation_thresholds": EXPECTED_THRESHOLDS,
            "holdout_for_threshold_tuning": False,
            "calibration_for_threshold_tuning": False,
            "production_promotion_authorized": False,
            "training_authorized": False,
        }

    def test_real_entry_state_holds_on_execution_prerequisites(self):
        result = build_stage1b_entry_audit(self.readiness(), self.thresholds())
        self.assertEqual(result["schema_version"], ENTRY_SCHEMA)
        self.assertEqual(result["entry_gate_status"], "HOLD")
        self.assertEqual(
            result["blockers"],
            [
                "SCORE_INPUT_REALIZATION_PENDING",
                "DETERMINISTIC_FEATURE_SCHEMA_PENDING",
                "TRAINING_PAYLOAD_MANIFEST_PENDING",
                "MODEL_IMPLEMENTATION_PENDING",
            ],
        )
        self.assertFalse(result["model_training_started"])
        self.assertFalse(result["training_authorized"])
        self.assertFalse(result["production_authority"])

    def test_threshold_tamper_fails_closed(self):
        thresholds = self.thresholds()
        thresholds["validation_thresholds"] = dict(EXPECTED_THRESHOLDS)
        thresholds["validation_thresholds"]["EXACT_NORMALIZED_LABEL_MATCH"] = 0.0
        with self.assertRaises(Stage1BEntryError):
            build_stage1b_entry_audit(self.readiness(), thresholds)

    def test_leakage_regression_fails_closed(self):
        readiness = self.readiness()
        readiness["leakage_gate"] = "HOLD"
        with self.assertRaises(Stage1BEntryError):
            build_stage1b_entry_audit(readiness, self.thresholds())

    def test_upstream_training_authority_escalation_fails_closed(self):
        readiness = self.readiness()
        readiness["training_authorized"] = True
        with self.assertRaises(Stage1BEntryError):
            build_stage1b_entry_audit(readiness, self.thresholds())


if __name__ == "__main__":
    unittest.main()
