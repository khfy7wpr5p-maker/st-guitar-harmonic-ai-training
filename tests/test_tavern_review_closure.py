from __future__ import annotations

import copy
import unittest

from st_harmonic_training.tavern_review_closure import (
    TavernReviewClosureError,
    build_tavern_review_resolution_plan,
    canonical_tavern_review_resolution_plan_json,
    validate_tavern_review_closure_summary,
)
from st_harmonic_training.tavern_structure import PINNED_TAVERN_REVISION


class TavernReviewClosureTests(unittest.TestCase):
    def summary(self) -> dict[str, object]:
        return {
            "schema_version": "st-tavern-human-review-closure-summary-v1",
            "source_corpus": "TAVERN",
            "source_revision": PINNED_TAVERN_REVISION,
            "comparison_evidence_sha256": "a" * 64,
            "reviewer_ref": "reviewer-opaque-001",
            "all_records_reviewed_by_human": True,
            "manual_refill_required": False,
            "manual_review_collection_status": "CLOSED_WITH_PDF_CAPTURE_LOSS",
            "total_pair_count": 3,
            "persisted_human_decision_count": 2,
            "stage0m_valid_human_decision_count": 1,
            "value_not_persisted_count": 1,
            "schema_incompatible_captured_choice_count": 1,
            "captured_decision_counts": {
                "SELECT_B": 1,
                "PRESERVE_VARIANTS": 1,
            },
            "contract_status_counts": {
                "CAPTURED_HUMAN_CHOICE_SCHEMA_INCOMPATIBLE_EQUIVALENT_PAIR": 1,
                "USER_ATTESTED_REVIEWED_BUT_VALUE_NOT_PERSISTED": 1,
                "VALID_STAGE0M_HUMAN_DECISION": 1,
            },
            "artifact_hashes": {
                "part1_pdf_sha256": "1" * 64,
                "part2_pdf_sha256": "2" * 64,
                "closure_json_sha256": "3" * 64,
                "validated_decisions_json_sha256": "4" * 64,
                "bundle_zip_sha256": "5" * 64,
            },
            "gold_assignment_authorized": False,
            "partition_assignment_authorized": False,
            "training_authorized": False,
        }

    def validate(self, data: dict[str, object] | None = None) -> dict[str, object]:
        return validate_tavern_review_closure_summary(
            data or self.summary(),
            expected_total_pair_count=3,
            expected_comparison_sha256="a" * 64,
        )

    def plan(self, data: dict[str, object] | None = None) -> dict[str, object]:
        return build_tavern_review_resolution_plan(
            data or self.summary(),
            expected_total_pair_count=3,
            expected_comparison_sha256="a" * 64,
        )

    def test_valid_closure_preserves_capture_loss(self) -> None:
        summary = self.validate()
        self.assertEqual(summary["stage0m_valid_human_decision_count"], 1)
        self.assertEqual(summary["value_not_persisted_count"], 1)
        self.assertFalse(summary["training_authorized"])

    def test_resolution_plan_quarantines_nonrecoverable_records(self) -> None:
        plan = self.plan()
        self.assertEqual(
            plan["disposition_counts"],
            {
                "ADMISSIBLE_STAGE0M_HUMAN_INPUT": 1,
                "QUARANTINE_PDF_CAPTURE_LOSS": 1,
                "QUARANTINE_SCHEMA_INCOMPATIBLE_CHOICE": 1,
            },
        )
        self.assertEqual(plan["eligible_for_gold_mapping_count"], 1)
        self.assertEqual(plan["quarantined_count"], 2)
        self.assertFalse(plan["gold_assignment_authorized"])
        self.assertFalse(plan["training_authorized"])

    def test_capture_loss_is_never_filled_by_inference(self) -> None:
        plan = self.plan()
        self.assertEqual(plan["capture_loss_policy"], "QUARANTINE_NO_INFERENCE_NO_REFILL")
        self.assertEqual(plan["schema_incompatible_policy"], "QUARANTINE_NO_AUTOMATIC_EQUIVALENCE_PROMOTION")

    def test_authority_escalation_fails_closed(self) -> None:
        for field in (
            "gold_assignment_authorized",
            "partition_assignment_authorized",
            "training_authorized",
        ):
            data = self.summary()
            data[field] = True
            with self.assertRaises(TavernReviewClosureError):
                self.validate(data)

    def test_count_tamper_fails_closed(self) -> None:
        data = self.summary()
        data["value_not_persisted_count"] = 0
        with self.assertRaises(TavernReviewClosureError):
            self.validate(data)

    def test_decision_count_tamper_fails_closed(self) -> None:
        data = self.summary()
        data["captured_decision_counts"] = {"SELECT_B": 1}
        with self.assertRaises(TavernReviewClosureError):
            self.validate(data)

    def test_status_count_tamper_fails_closed(self) -> None:
        data = self.summary()
        data["contract_status_counts"] = {
            "VALID_STAGE0M_HUMAN_DECISION": 3,
        }
        with self.assertRaises(TavernReviewClosureError):
            self.validate(data)

    def test_artifact_hash_key_tamper_fails_closed(self) -> None:
        data = self.summary()
        artifact_hashes = copy.deepcopy(data["artifact_hashes"])
        artifact_hashes.pop("bundle_zip_sha256")
        data["artifact_hashes"] = artifact_hashes
        with self.assertRaises(TavernReviewClosureError):
            self.validate(data)

    def test_wrong_comparison_digest_fails_closed(self) -> None:
        data = self.summary()
        data["comparison_evidence_sha256"] = "b" * 64
        with self.assertRaises(TavernReviewClosureError):
            self.validate(data)

    def test_missing_human_review_attestation_fails_closed(self) -> None:
        data = self.summary()
        data["all_records_reviewed_by_human"] = False
        with self.assertRaises(TavernReviewClosureError):
            self.validate(data)

    def test_manual_refill_cannot_reopen_silently(self) -> None:
        data = self.summary()
        data["manual_refill_required"] = True
        with self.assertRaises(TavernReviewClosureError):
            self.validate(data)

    def test_canonical_plan_json_is_deterministic(self) -> None:
        left = self.plan()
        right_data = self.summary()
        right_data["captured_decision_counts"] = {
            "PRESERVE_VARIANTS": 1,
            "SELECT_B": 1,
        }
        right = self.plan(right_data)
        self.assertEqual(
            canonical_tavern_review_resolution_plan_json(left),
            canonical_tavern_review_resolution_plan_json(right),
        )


if __name__ == "__main__":
    unittest.main()
