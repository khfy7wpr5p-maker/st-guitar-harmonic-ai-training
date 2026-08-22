from __future__ import annotations

import copy
import unittest

from st_harmonic_training.baseline_thresholds import (
    BASELINE_SCHEMA,
    PINNED_BASELINE_TARGET_SHA256,
    THRESHOLD_SCHEMA,
    BaselineThresholdError,
    build_majority_target_baseline,
    build_promotion_thresholds,
)
from st_harmonic_training.normalization import NORMALIZED_FIELDS, NORMALIZATION_VERSION
from st_harmonic_training.tavern_normalization_adapter import NORMALIZED_TARGET_SCHEMA
from st_harmonic_training.tavern_readiness_completion import (
    COMPLETION_SCHEMA,
    PINNED_NORMALIZED_TARGET_MANIFEST_SHA256,
)
from st_harmonic_training.tavern_reviewed_split import (
    EXPECTED_RECORD_DISTRIBUTION,
    EXPECTED_SEED,
    SPLIT_SCHEMA,
)
from st_harmonic_training.tavern_structure import PINNED_TAVERN_REVISION


def label(index: int, *, phrase: str | None = None, roman: str | None = None) -> dict[str, object]:
    result = {field: None for field in NORMALIZED_FIELDS}
    result["key"] = f"K{index}:"
    result["roman_numeral"] = roman if roman is not None else f'["R{index}"]'
    result["phrase"] = phrase if phrase is not None else f'["F{index}"]'
    return result


BASELINE_LABEL = {field: None for field in NORMALIZED_FIELDS}
BASELINE_LABEL.update(
    {
        "key": "D:",
        "roman_numeral": '["I","I","C64","V7","I"]',
        "phrase": '["T","D","T"]',
    }
)


class BaselineBuilderTests(unittest.TestCase):
    def payloads(self):
        target_records = []
        split_records = []
        partitions = (
            ["TRAIN"] * 487
            + ["VALIDATION"] * 125
            + ["CALIBRATION"] * 41
            + ["HOLDOUT"] * 41
        )
        for index, partition in enumerate(partitions):
            phrase_key = f"Synthetic/W{index:03d}:00:01"
            targets = []
            if partition == "TRAIN" and index < 13:
                targets.append({"normalized_st_label": copy.deepcopy(BASELINE_LABEL)})
            elif partition == "VALIDATION":
                val_index = index - 487
                function = '["T","D","T"]' if val_index < 5 else f'["VF{val_index}"]'
                targets.append(
                    {
                        "normalized_st_label": label(
                            10_000 + index,
                            phrase=function,
                            roman=f'["VR{val_index}"]',
                        )
                    }
                )
            else:
                targets.append({"normalized_st_label": label(index)})

            if partition == "TRAIN" and 13 <= index < 26:
                targets.append({"normalized_st_label": label(20_000 + index)})
            if partition == "VALIDATION" and (index - 487) < 29:
                targets.append({"normalized_st_label": label(30_000 + index)})

            target_records.append({"phrase_key": phrase_key, "targets": targets})
            split_records.append({"phrase_key": phrase_key, "partition": partition})

        normalized = {
            "schema_version": NORMALIZED_TARGET_SCHEMA,
            "source_corpus": "TAVERN_REVIEWED_694",
            "source_revision": PINNED_TAVERN_REVISION,
            "validated_human_decisions_sha256": "a" * 64,
            "normalization_version": NORMALIZATION_VERSION,
            "normalized_target_manifest_sha256": PINNED_NORMALIZED_TARGET_MANIFEST_SHA256,
            "records": target_records,
            "training_authorized": False,
        }
        split = {
            "schema_version": SPLIT_SCHEMA,
            "source_corpus": "TAVERN_REVIEWED_694",
            "source_revision": PINNED_TAVERN_REVISION,
            "validated_human_decisions_sha256": "a" * 64,
            "seed": EXPECTED_SEED,
            "record_distribution": EXPECTED_RECORD_DISTRIBUTION,
            "records": split_records,
            "training_authorized": False,
        }
        return normalized, split

    def test_majority_baseline_uses_train_and_validation_only(self):
        normalized, split = self.payloads()
        result = build_majority_target_baseline(normalized, split)
        self.assertEqual(result["fit_partition"], "TRAIN")
        self.assertEqual(result["evaluation_partition"], "VALIDATION")
        self.assertFalse(result["calibration_accessed"])
        self.assertFalse(result["holdout_accessed"])
        self.assertEqual(result["train_target_count"], 500)
        self.assertEqual(result["validation_target_count"], 154)
        self.assertEqual(
            result["metrics"],
            {
                "EXACT_NORMALIZED_LABEL_MATCH": 0.0,
                "VARIANT_AWARE_ACCEPTABLE_SET_ACCURACY": 0.0,
                "ROMAN_NUMERAL_COMPONENT_ACCURACY": 0.0,
                "FUNCTIONAL_COMPONENT_ACCURACY": 0.04,
            },
        )

    def test_split_seed_tamper_fails_closed(self):
        normalized, split = self.payloads()
        split["seed"] = "tampered"
        with self.assertRaises(BaselineThresholdError):
            build_majority_target_baseline(normalized, split)

    def test_upstream_training_authority_escalation_fails_closed(self):
        normalized, split = self.payloads()
        normalized["training_authorized"] = True
        with self.assertRaises(BaselineThresholdError):
            build_majority_target_baseline(normalized, split)


class PromotionThresholdTests(unittest.TestCase):
    def readiness(self):
        return {
            "schema_version": COMPLETION_SCHEMA,
            "dataset_readiness_gate": "PASS",
            "training_payload_ready": True,
            "training_authorized": False,
        }

    def baseline(self):
        return {
            "schema_version": BASELINE_SCHEMA,
            "fit_partition": "TRAIN",
            "evaluation_partition": "VALIDATION",
            "calibration_accessed": False,
            "holdout_accessed": False,
            "baseline_target_sha256": PINNED_BASELINE_TARGET_SHA256,
            "train_record_count": 487,
            "validation_record_count": 125,
            "train_target_count": 500,
            "validation_target_count": 154,
            "train_variant_record_count": 13,
            "validation_variant_record_count": 29,
            "unique_train_target_count": 435,
            "baseline_train_frequency": 13,
            "metrics": {
                "EXACT_NORMALIZED_LABEL_MATCH": 0.0,
                "VARIANT_AWARE_ACCEPTABLE_SET_ACCURACY": 0.0,
                "ROMAN_NUMERAL_COMPONENT_ACCURACY": 0.0,
                "FUNCTIONAL_COMPONENT_ACCURACY": 0.04,
            },
        }

    def test_real_baseline_freezes_shadow_only_thresholds(self):
        result = build_promotion_thresholds(self.readiness(), self.baseline())
        self.assertEqual(result["schema_version"], THRESHOLD_SCHEMA)
        self.assertEqual(result["promotion_scope"], "OFFLINE_SHADOW_ONLY")
        self.assertEqual(result["promotion_threshold_status"], "FROZEN")
        self.assertFalse(result["production_promotion_authorized"])
        self.assertFalse(result["holdout_for_threshold_tuning"])
        self.assertFalse(result["training_authorized"])

    def test_holdout_baseline_access_fails_closed(self):
        baseline = self.baseline()
        baseline["holdout_accessed"] = True
        with self.assertRaises(BaselineThresholdError):
            build_promotion_thresholds(self.readiness(), baseline)

    def test_dataset_readiness_must_pass(self):
        readiness = self.readiness()
        readiness["dataset_readiness_gate"] = "HOLD"
        with self.assertRaises(BaselineThresholdError):
            build_promotion_thresholds(readiness, self.baseline())


if __name__ == "__main__":
    unittest.main()
