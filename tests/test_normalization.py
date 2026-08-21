from __future__ import annotations

import unittest

from st_harmonic_training.contracts import ContractError
from st_harmonic_training.normalization import (
    NORMALIZATION_VERSION,
    build_normalization_record,
)


class NormalizationTests(unittest.TestCase):
    def test_raw_source_label_is_preserved_exactly(self) -> None:
        raw = "  V  6/5  -> source spelling  "
        record = build_normalization_record(raw, {"roman_numeral": " V  6/5 "})
        self.assertEqual(record.raw_source_label, raw)
        self.assertEqual(record.normalized_st_label.roman_numeral, "V 6/5")

    def test_normalization_is_deterministic(self) -> None:
        mapping = {
            "key": " C   major ",
            "local_key": " G major ",
            "roman_numeral": " V7 ",
            "bass": " G ",
            "inversion": " root ",
            "chord_family": " dominant ",
            "extension": " 7 ",
            "suspension": None,
            "alteration": None,
            "phrase": " antecedent ",
            "cadence": " HC ",
        }
        a = build_normalization_record("V7", mapping)
        b = build_normalization_record("V7", mapping)
        self.assertEqual(a, b)
        self.assertEqual(a.normalization_version, NORMALIZATION_VERSION)

    def test_unknown_semantic_field_fails_closed(self) -> None:
        with self.assertRaises(ContractError):
            build_normalization_record("V", {"invented_authoritative_chord": "V"})

    def test_unversioned_semantic_change_is_rejected(self) -> None:
        with self.assertRaises(ContractError):
            build_normalization_record(
                "V",
                {"roman_numeral": "V"},
                normalization_version="st-harmony-normalization-v2-unregistered",
            )


if __name__ == "__main__":
    unittest.main()
