from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from st_harmonic_training.specialist_contract import (
    FIRST_WAVE_SPECIALISTS,
    SpecialistContractError,
    build_specialist_contract,
    validate_specialist_contract,
)


class SpecialistContractTests(unittest.TestCase):
    def test_first_wave_is_exactly_three_supported_specialists(self) -> None:
        self.assertEqual(
            [item["specialist_id"] for item in FIRST_WAVE_SPECIALISTS],
            [
                "ROMAN_NUMERAL_SPECIALIST",
                "KEY_SPECIALIST",
                "FUNCTION_SPECIALIST",
            ],
        )
        self.assertEqual(
            [item["target_field"] for item in FIRST_WAVE_SPECIALISTS],
            ["roman_numeral", "key", "phrase"],
        )

    def test_contract_keeps_all_authority_closed(self) -> None:
        contract = validate_specialist_contract(build_specialist_contract())
        self.assertFalse(contract["training_authorized"])
        self.assertFalse(contract["calibration_access_authorized"])
        self.assertFalse(contract["holdout_access_authorized"])
        self.assertFalse(contract["event_level_training_authorized"])
        self.assertFalse(contract["production_authority"])
        self.assertTrue(contract["deterministic_resolver_remains_authoritative"])
        self.assertEqual(contract["development_policy"]["fit_partition"], "TRAIN_ONLY")
        self.assertTrue(contract["development_policy"]["grouped_internal_cv_required"])
        self.assertFalse(
            contract["development_policy"]["original_validation_reuse_during_iteration"]
        )

    def test_unsupported_specialist_promotion_fails_closed(self) -> None:
        contract = build_specialist_contract()
        cadence = next(
            item
            for item in contract["deferred_specialists"]
            if item["specialist_id"] == "CADENCE_SPECIALIST"
        )
        contract["first_wave_specialists"].append(cadence)
        with self.assertRaises(SpecialistContractError):
            validate_specialist_contract(contract)

    def test_training_authority_escalation_fails_closed(self) -> None:
        contract = build_specialist_contract()
        contract["training_authorized"] = True
        with self.assertRaises(SpecialistContractError):
            validate_specialist_contract(contract)

    def test_source_support_count_tamper_fails_closed(self) -> None:
        contract = build_specialist_contract()
        tampered = copy.deepcopy(contract)
        tampered["first_wave_specialists"][1]["supported_target_count"] = 747
        with self.assertRaises(SpecialistContractError):
            validate_specialist_contract(tampered)

    def test_committed_contract_evidence_matches_generator(self) -> None:
        root = Path(__file__).resolve().parents[1]
        evidence = json.loads(
            (root / "evidence" / "stage2a_specialist_contract.v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(evidence, build_specialist_contract())
        validate_specialist_contract(evidence)


if __name__ == "__main__":
    unittest.main()
