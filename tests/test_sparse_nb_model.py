from __future__ import annotations

import copy
import unittest

from st_harmonic_training.normalization import NORMALIZED_FIELDS
from st_harmonic_training.sparse_nb_model import (
    SCORE_SEMANTICS,
    SparseNBModelError,
    canonical_model_json,
    fit_fieldwise_sparse_nb,
    predict_fieldwise_sparse_nb,
)


def label(roman: str, phrase: str | None = None) -> dict[str, object]:
    result = {field: None for field in NORMALIZED_FIELDS}
    result["key"] = "C:"
    result["roman_numeral"] = roman
    result["phrase"] = phrase
    return result


class SparseNBModelTests(unittest.TestCase):
    def examples(self):
        return [
            {
                "phrase_key": "A:00:01",
                "partition": "TRAIN",
                "features": {"KERN_ATOM::4c": 2, "BARLINE": 1},
                "targets": [label('["I"]', '["T"]')],
            },
            {
                "phrase_key": "B:00:01",
                "partition": "TRAIN",
                "features": {"KERN_ATOM::4g": 3, "BARLINE": 1},
                "targets": [
                    label('["V"]', '["D"]'),
                    label('["V7"]', '["D"]'),
                ],
            },
        ]

    def test_fit_is_deterministic_across_example_order(self) -> None:
        left = fit_fieldwise_sparse_nb(self.examples())
        right = fit_fieldwise_sparse_nb(list(reversed(self.examples())))
        self.assertEqual(canonical_model_json(left), canonical_model_json(right))
        self.assertEqual(left["variant_training_example_count"], 1)
        self.assertFalse(left["untrusted_pickle_loading_allowed"])
        self.assertFalse(left["calibrated_probability_output"])

    def test_variant_targets_contribute_equal_weight_without_collapse(self) -> None:
        model = fit_fieldwise_sparse_nb(self.examples())
        roman_classes = model["fields"]["roman_numeral"]["classes"]
        weights = {item["class_key"]: item["class_weight"] for item in roman_classes}
        self.assertEqual(weights['"[\\"I\\"]"'], 1.0)
        self.assertEqual(weights['"[\\"V\\"]"'], 0.5)
        self.assertEqual(weights['"[\\"V7\\"]"'], 0.5)

    def test_fit_rejects_non_train_label_access(self) -> None:
        examples = self.examples()
        examples[0]["partition"] = "VALIDATION"
        with self.assertRaises(SparseNBModelError):
            fit_fieldwise_sparse_nb(examples)

    def test_prediction_exposes_model_score_not_probability(self) -> None:
        model = fit_fieldwise_sparse_nb(self.examples())
        result = predict_fieldwise_sparse_nb(
            model, {"KERN_ATOM::4c": 1, "BARLINE": 1}
        )
        self.assertEqual(result["score_semantics"], SCORE_SEMANTICS)
        self.assertIsNone(result["calibrated_probability"])
        self.assertFalse(result["authoritative_decision"])
        self.assertEqual(
            result["field_scores"]["roman_numeral"]["score_semantics"],
            SCORE_SEMANTICS,
        )

    def test_model_tamper_fails_closed(self) -> None:
        model = fit_fieldwise_sparse_nb(self.examples())
        model = copy.deepcopy(model)
        model["calibrated_probability_output"] = True
        with self.assertRaises(SparseNBModelError):
            predict_fieldwise_sparse_nb(model, {"KERN_ATOM::4c": 1})

    def test_feature_bounds_reject_negative_counts(self) -> None:
        examples = self.examples()
        examples[0]["features"] = {"KERN_ATOM::4c": -1}
        with self.assertRaises(SparseNBModelError):
            fit_fieldwise_sparse_nb(examples)


if __name__ == "__main__":
    unittest.main()
