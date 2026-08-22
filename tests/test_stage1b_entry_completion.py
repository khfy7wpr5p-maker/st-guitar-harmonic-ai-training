from __future__ import annotations

import copy
import unittest

from st_harmonic_training.baseline_thresholds import THRESHOLD_SCHEMA
from st_harmonic_training.sparse_nb_model import (
    MODEL_IMPLEMENTATION_VERSION,
    MODEL_SEED,
    SCORE_SEMANTICS,
)
from st_harmonic_training.stage1b_entry_completion import (
    ENTRY_COMPLETION_SCHEMA,
    ENVIRONMENT_LOCK_SCHEMA,
    EXPECTED_FEATURE_MANIFEST_SHA256,
    EXPECTED_NORMALIZED_TARGET_MANIFEST_SHA256,
    EXPECTED_PARTITIONS,
    EXPECTED_SCORE_INPUT_MANIFEST_SHA256,
    EXPECTED_THRESHOLDS,
    MODEL_EVIDENCE_SCHEMA,
    Stage1BEntryCompletionError,
    build_stage1b_entry_completion,
)
from st_harmonic_training.tavern_kern_features import (
    ADAPTER_VERSION as FEATURE_ADAPTER_VERSION,
    SUMMARY_SCHEMA as FEATURE_SUMMARY_SCHEMA,
)
from st_harmonic_training.tavern_readiness_completion import COMPLETION_SCHEMA
from st_harmonic_training.tavern_score_input_realization import SUMMARY_SCHEMA as SCORE_SUMMARY_SCHEMA
from st_harmonic_training.tavern_structure import PINNED_TAVERN_REVISION
from st_harmonic_training.training_payload import (
    PINNED_TRAINING_PAYLOAD_MANIFEST_SHA256,
    SUMMARY_SCHEMA as PAYLOAD_SUMMARY_SCHEMA,
)


class Stage1BEntryCompletionTests(unittest.TestCase):
    def dataset(self):
        return {
            "schema_version": COMPLETION_SCHEMA,
            "source_corpus": "TAVERN_REVIEWED_694",
            "source_revision": PINNED_TAVERN_REVISION,
            "dataset_readiness_gate": "PASS",
            "leakage_gate": "PASS",
            "training_payload_ready": True,
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
        }

    def score(self):
        return {
            "schema_version": SCORE_SUMMARY_SCHEMA,
            "source_corpus": "TAVERN_REVIEWED_694",
            "source_revision": PINNED_TAVERN_REVISION,
            "record_count": 694,
            "score_input_realization_complete": True,
            "score_input_manifest_sha256": EXPECTED_SCORE_INPUT_MANIFEST_SHA256,
            "training_authorized": False,
        }

    def feature(self):
        return {
            "schema_version": FEATURE_SUMMARY_SCHEMA,
            "source_corpus": "TAVERN_REVIEWED_694",
            "source_revision": PINNED_TAVERN_REVISION,
            "record_count": 694,
            "adapter_version": FEATURE_ADAPTER_VERSION,
            "feature_manifest_sha256": EXPECTED_FEATURE_MANIFEST_SHA256,
            "score_input_manifest_sha256": EXPECTED_SCORE_INPUT_MANIFEST_SHA256,
            "deterministic_feature_schema_complete": True,
            "training_authorized": False,
        }

    def payload(self):
        return {
            "schema_version": PAYLOAD_SUMMARY_SCHEMA,
            "source_corpus": "TAVERN_REVIEWED_694",
            "source_revision": PINNED_TAVERN_REVISION,
            "record_count": 694,
            "target_count": 747,
            "partition_distribution": EXPECTED_PARTITIONS,
            "feature_manifest_sha256": EXPECTED_FEATURE_MANIFEST_SHA256,
            "normalized_target_manifest_sha256": EXPECTED_NORMALIZED_TARGET_MANIFEST_SHA256,
            "training_payload_manifest_sha256": PINNED_TRAINING_PAYLOAD_MANIFEST_SHA256,
            "training_payload_manifest_complete": True,
            "holdout_labels_available_to_training": False,
            "holdout_labels_available_to_model_selection": False,
            "calibration_labels_available_to_parameter_fitting": False,
            "augmentation_scope": "TRAIN_ONLY",
            "training_authorized": False,
        }

    def model(self):
        return {
            "schema_version": MODEL_EVIDENCE_SCHEMA,
            "model_implementation_complete": True,
            "implementation_version": MODEL_IMPLEMENTATION_VERSION,
            "model_seed": MODEL_SEED,
            "score_semantics": SCORE_SEMANTICS,
            "fit_partition": "TRAIN",
            "evaluation_partition": "VALIDATION",
            "variant_policy": "EQUAL_MASS_SET_VALUED_TARGETS",
            "untrusted_pickle_loading_allowed": False,
            "calibrated_probability_output": False,
            "model_training_started": False,
            "training_authorized": False,
            "production_authority": False,
        }

    def environment(self):
        return {
            "schema_version": ENVIRONMENT_LOCK_SCHEMA,
            "python_version": "3.12.8",
            "dependencies": [],
            "stdlib_only": True,
            "implementation_version": MODEL_IMPLEMENTATION_VERSION,
            "model_seed": MODEL_SEED,
            "checkpoint_format": "CANONICAL_JSON_ONLY",
            "pickle_loading_allowed": False,
        }

    def build(self):
        return build_stage1b_entry_completion(
            self.dataset(), self.thresholds(), self.score(), self.feature(),
            self.payload(), self.model(), self.environment()
        )

    def test_real_contract_state_passes_offline_only(self) -> None:
        result = self.build()
        self.assertEqual(result["schema_version"], ENTRY_COMPLETION_SCHEMA)
        self.assertEqual(result["entry_gate_status"], "PASS")
        self.assertEqual(result["training_scope"], "OFFLINE_EXPERIMENT_ONLY")
        self.assertTrue(result["training_authorized"])
        self.assertFalse(result["model_training_started"])
        self.assertFalse(result["production_authority"])
        self.assertFalse(result["holdout_access_during_training"])

    def test_holdout_exposure_fails_closed(self) -> None:
        payload = self.payload()
        payload["holdout_labels_available_to_training"] = True
        with self.assertRaises(Stage1BEntryCompletionError):
            build_stage1b_entry_completion(
                self.dataset(), self.thresholds(), self.score(), self.feature(),
                payload, self.model(), self.environment()
            )

    def test_threshold_tamper_fails_closed(self) -> None:
        thresholds = self.thresholds()
        thresholds["validation_thresholds"] = dict(EXPECTED_THRESHOLDS)
        thresholds["validation_thresholds"]["ROMAN_NUMERAL_COMPONENT_ACCURACY"] = 0.0
        with self.assertRaises(Stage1BEntryCompletionError):
            build_stage1b_entry_completion(
                self.dataset(), thresholds, self.score(), self.feature(),
                self.payload(), self.model(), self.environment()
            )

    def test_dependency_addition_fails_closed(self) -> None:
        environment = self.environment()
        environment["dependencies"] = ["numpy"]
        environment["stdlib_only"] = False
        with self.assertRaises(Stage1BEntryCompletionError):
            build_stage1b_entry_completion(
                self.dataset(), self.thresholds(), self.score(), self.feature(),
                self.payload(), self.model(), environment
            )

    def test_model_authority_escalation_fails_closed(self) -> None:
        model = copy.deepcopy(self.model())
        model["production_authority"] = True
        with self.assertRaises(Stage1BEntryCompletionError):
            build_stage1b_entry_completion(
                self.dataset(), self.thresholds(), self.score(), self.feature(),
                self.payload(), model, self.environment()
            )


if __name__ == "__main__":
    unittest.main()
