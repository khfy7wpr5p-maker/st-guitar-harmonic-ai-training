from __future__ import annotations

import copy
import unittest

from st_harmonic_training.tavern_gold_materialization import PINNED_VALIDATED_SHA256
from st_harmonic_training.tavern_normalization_adapter import ADAPTER_VERSION
from st_harmonic_training.tavern_raw_label_realization import PINNED_TAVERN_ARCHIVE_SHA256
from st_harmonic_training.tavern_readiness_completion import (
    PINNED_NORMALIZED_TARGET_MANIFEST_SHA256,
    PINNED_REALIZATION_MANIFEST_SHA256,
    TavernReadinessCompletionError,
    build_tavern_dataset_readiness_completion,
    canonical_tavern_dataset_readiness_completion_json,
)
from st_harmonic_training.tavern_reviewed_split import EXPECTED_RECORD_DISTRIBUTION, EXPECTED_SEED
from st_harmonic_training.tavern_structure import PINNED_TAVERN_REVISION


class TavernReadinessCompletionTests(unittest.TestCase):
    def audit(self) -> dict[str, object]:
        return {
            "schema_version": "st-tavern-final-readiness-audit-v1",
            "source_corpus": "TAVERN_REVIEWED_694",
            "source_revision": PINNED_TAVERN_REVISION,
            "validated_human_decisions_sha256": PINNED_VALIDATED_SHA256,
            "eligible_record_count": 694,
            "gold_tier_counts": {"GOLD_EXPERT": 641, "GOLD_VARIANT": 53},
            "split_seed": EXPECTED_SEED,
            "split_distribution": EXPECTED_RECORD_DISTRIBUTION,
            "leakage_gate": "PASS",
            "gate_status": "HOLD",
            "blockers": [
                "RAW_LABEL_REALIZATION_PENDING",
                "DETERMINISTIC_NORMALIZATION_PENDING",
            ],
            "raw_label_realization_complete": False,
            "normalization_complete": False,
            "training_authorized": False,
        }

    def realization(self) -> dict[str, object]:
        return {
            "schema_version": "st-tavern-raw-label-realization-summary-v1",
            "source_corpus": "TAVERN_REVIEWED_694",
            "source_revision": PINNED_TAVERN_REVISION,
            "archive_sha256": PINNED_TAVERN_ARCHIVE_SHA256,
            "validated_human_decisions_sha256": PINNED_VALIDATED_SHA256,
            "record_count": 694,
            "selected_label_count": 747,
            "selected_source_counts": {"A": 55, "B": 692},
            "realization_manifest_sha256": PINNED_REALIZATION_MANIFEST_SHA256,
            "raw_label_realization_complete": True,
            "normalization_complete": False,
            "training_authorized": False,
        }

    def normalization(self) -> dict[str, object]:
        return {
            "schema_version": "st-tavern-normalized-targets-summary-v1",
            "adapter_version": ADAPTER_VERSION,
            "normalization_version": "st-harmony-normalization-v1",
            "source_corpus": "TAVERN_REVIEWED_694",
            "source_revision": PINNED_TAVERN_REVISION,
            "archive_sha256": PINNED_TAVERN_ARCHIVE_SHA256,
            "validated_human_decisions_sha256": PINNED_VALIDATED_SHA256,
            "record_count": 694,
            "normalized_target_count": 747,
            "normalized_target_manifest_sha256": PINNED_NORMALIZED_TARGET_MANIFEST_SHA256,
            "raw_label_realization_complete": True,
            "normalization_complete": True,
            "partition_assignment_authorized": False,
            "training_authorized": False,
        }

    def build(self):
        return build_tavern_dataset_readiness_completion(
            self.audit(), self.realization(), self.normalization()
        )

    def test_dataset_readiness_passes_but_model_training_stays_closed(self) -> None:
        result = self.build()
        self.assertEqual(result["dataset_readiness_gate"], "PASS")
        self.assertEqual(result["remaining_dataset_blockers"], [])
        self.assertTrue(result["raw_label_realization_complete"])
        self.assertTrue(result["normalization_complete"])
        self.assertTrue(result["training_payload_ready"])
        self.assertEqual(
            result["next_required_gate"], "PROMOTION_THRESHOLDS_PENDING_BASELINE"
        )
        self.assertFalse(result["model_training_started"])
        self.assertFalse(result["model_training_authorized"])
        self.assertFalse(result["training_authorized"])

    def test_realization_manifest_tamper_fails_closed(self) -> None:
        data = self.realization()
        data["realization_manifest_sha256"] = "0" * 64
        with self.assertRaises(TavernReadinessCompletionError):
            build_tavern_dataset_readiness_completion(
                self.audit(), data, self.normalization()
            )

    def test_incomplete_normalization_fails_closed(self) -> None:
        data = self.normalization()
        data["normalization_complete"] = False
        with self.assertRaises(TavernReadinessCompletionError):
            build_tavern_dataset_readiness_completion(
                self.audit(), self.realization(), data
            )

    def test_leakage_gate_regression_fails_closed(self) -> None:
        data = self.audit()
        data["leakage_gate"] = "HOLD"
        with self.assertRaises(TavernReadinessCompletionError):
            build_tavern_dataset_readiness_completion(
                data, self.realization(), self.normalization()
            )

    def test_upstream_authority_escalation_fails_closed(self) -> None:
        data = self.normalization()
        data["training_authorized"] = True
        with self.assertRaises(TavernReadinessCompletionError):
            build_tavern_dataset_readiness_completion(
                self.audit(), self.realization(), data
            )

    def test_output_is_deterministic(self) -> None:
        left = self.build()
        right = build_tavern_dataset_readiness_completion(
            copy.deepcopy(self.audit()),
            copy.deepcopy(self.realization()),
            copy.deepcopy(self.normalization()),
        )
        self.assertEqual(
            canonical_tavern_dataset_readiness_completion_json(left),
            canonical_tavern_dataset_readiness_completion_json(right),
        )


if __name__ == "__main__":
    unittest.main()
