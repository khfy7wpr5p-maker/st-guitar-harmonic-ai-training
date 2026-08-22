from __future__ import annotations

import copy
import unittest

from st_harmonic_training.tavern_readiness_audit import (
    TavernReadinessAuditError,
    build_tavern_final_readiness_audit,
    canonical_tavern_readiness_audit_json,
)
from st_harmonic_training.tavern_structure import PINNED_TAVERN_REVISION
from st_harmonic_training.tavern_gold_materialization import PINNED_VALIDATED_SHA256


class TavernReadinessAuditTests(unittest.TestCase):
    def material(self):
        return {
            "schema_version":"st-tavern-gold-materialization-summary-v1","source_corpus":"TAVERN",
            "source_revision":PINNED_TAVERN_REVISION,"validated_human_decisions_sha256":PINNED_VALIDATED_SHA256,
            "record_count":694,"gold_tier_counts":{"GOLD_EXPERT":641,"GOLD_VARIANT":53},
            "hash_bound_external_label_pending_count":694,"normalization_version":"st-harmony-normalization-v1",
            "gold_assignment_authorized":True,"partition_assignment_authorized":False,"training_authorized":False,
        }
    def admission(self, raw=False, normalized=False):
        return {
            "schema_version":"st-tavern-reviewed-subset-admission-v1","subset_corpus":"TAVERN_REVIEWED_694",
            "source_revision":PINNED_TAVERN_REVISION,"admitted_record_count":694,"excluded_record_count":243,
            "gold_tier_counts":{"GOLD_EXPERT":641,"GOLD_VARIANT":53},"admission_scope":"DATASET_ENGINEERING_ONLY",
            "raw_label_realization_complete":raw,"normalization_complete":normalized,
            "partition_assignment_authorized":False,"training_authorized":False,
        }
    def lineage(self):
        return {
            "schema_version":"st-tavern-reviewed-lineage-closure-summary-v1","source_corpus":"TAVERN_REVIEWED_694",
            "source_revision":PINNED_TAVERN_REVISION,"validated_human_decisions_sha256":PINNED_VALIDATED_SHA256,
            "reviewed_record_count":694,"active_work_family_count":24,
            "inactive_documented_work_ids":["Beethoven/B071","Mozart/K025","Mozart/K179"],
            "cross_corpus_aliases_bound":True,"partition_assignment_authorized":False,"training_authorized":False,
        }
    def split(self):
        return {
            "schema_version":"st-tavern-reviewed-split-summary-v1","source_corpus":"TAVERN_REVIEWED_694",
            "source_revision":PINNED_TAVERN_REVISION,"validated_human_decisions_sha256":PINNED_VALIDATED_SHA256,
            "record_count":694,"record_distribution":{"CALIBRATION":41,"HOLDOUT":41,"TRAIN":487,"VALIDATION":125},
            "work_family_distribution":{"CALIBRATION":2,"HOLDOUT":2,"TRAIN":18,"VALIDATION":2},
            "seed":"st-tavern-split-v1:12","label_aware_seed_selection":False,
            "cross_corpus_alias_partition_inheritance_required":True,"augmentation_scope":"TRAIN_ONLY",
            "partition_assignment_authorized":True,"training_authorized":False,
        }

    def build(self, admission=None):
        return build_tavern_final_readiness_audit(self.material(), admission or self.admission(), self.lineage(), self.split())

    def test_real_state_holds_only_for_label_realization_and_normalization(self):
        report = self.build()
        self.assertEqual(report["gate_status"], "HOLD")
        self.assertEqual(report["blockers"], ["RAW_LABEL_REALIZATION_PENDING","DETERMINISTIC_NORMALIZATION_PENDING"])
        self.assertEqual(report["leakage_gate"], "PASS")
        self.assertTrue(report["teacher_gold_present_in_calibration"])
        self.assertTrue(report["teacher_gold_present_in_holdout"])
        self.assertFalse(report["training_authorized"])

    def test_hypothetical_completed_payload_can_pass(self):
        report = self.build(self.admission(raw=True, normalized=True))
        self.assertEqual(report["gate_status"], "PASS")
        self.assertEqual(report["blockers"], [])
        self.assertTrue(report["training_authorized"])

    def test_split_tamper_fails_closed(self):
        split = self.split(); split["record_distribution"]["HOLDOUT"] = 0
        with self.assertRaises(TavernReadinessAuditError):
            build_tavern_final_readiness_audit(self.material(), self.admission(), self.lineage(), split)

    def test_alias_boundary_tamper_fails_closed(self):
        lineage = self.lineage(); lineage["cross_corpus_aliases_bound"] = False
        with self.assertRaises(TavernReadinessAuditError):
            build_tavern_final_readiness_audit(self.material(), self.admission(), lineage, self.split())

    def test_upstream_training_authority_escalation_fails_closed(self):
        material = self.material(); material["training_authorized"] = True
        with self.assertRaises(TavernReadinessAuditError):
            build_tavern_final_readiness_audit(material, self.admission(), self.lineage(), self.split())

    def test_deterministic_output(self):
        left = canonical_tavern_readiness_audit_json(self.build())
        right = canonical_tavern_readiness_audit_json(build_tavern_final_readiness_audit(copy.deepcopy(self.material()), copy.deepcopy(self.admission()), copy.deepcopy(self.lineage()), copy.deepcopy(self.split())))
        self.assertEqual(left, right)


if __name__ == "__main__": unittest.main()
