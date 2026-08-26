from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest

from st_harmonic_training.stage2d_target_learnability import (
    Stage2DTargetLearnabilityError,
    _audit_specialist,
    _sequence_length,
)


class Stage2DTargetLearnabilityTests(unittest.TestCase):
    def _row(
        self,
        phrase: str,
        group: str,
        fold: int,
        *,
        roman: tuple[str, ...] = (),
        key: tuple[str, ...] = (),
        function: tuple[str, ...] = (),
    ) -> dict[str, object]:
        return {
            "phrase_key": phrase,
            "split_group_id": group,
            "development_fold": fold,
            "features": {"x": 1},
            "target_sets": {
                "ROMAN_NUMERAL_SPECIALIST": roman,
                "KEY_SPECIALIST": key,
                "FUNCTION_SPECIALIST": function,
            },
        }

    def test_sequence_length_uses_canonical_json_array(self) -> None:
        self.assertEqual(
            _sequence_length("ROMAN_NUMERAL_SPECIALIST", '["I","V7","I"]'),
            3,
        )
        self.assertEqual(_sequence_length("KEY_SPECIALIST", "C:"), 1)

    def test_malformed_sequence_target_fails_closed(self) -> None:
        with self.assertRaises(Stage2DTargetLearnabilityError):
            _sequence_length("FUNCTION_SPECIALIST", "T D T")
        with self.assertRaises(Stage2DTargetLearnabilityError):
            _sequence_length("ROMAN_NUMERAL_SPECIALIST", "[]")

    def test_unseen_fold_targets_reduce_closed_set_oracle_ceiling(self) -> None:
        common = '["I","V"]'
        unique = '["ii"]'
        rows = [
            self._row("p0", "g0", 0, roman=(common,)),
            self._row("p1", "g1", 1, roman=(common,)),
            self._row("p2", "g2", 2, roman=(unique,)),
        ]
        audit = _audit_specialist(rows, "ROMAN_NUMERAL_SPECIALIST")
        self.assertEqual(audit["eligible_record_count"], 3)
        self.assertEqual(audit["unique_target_count"], 2)
        self.assertEqual(audit["singleton_target_count"], 1)
        self.assertEqual(
            audit["target_fold_presence_distribution"],
            {"1": 1, "2": 1, "3": 0},
        )
        self.assertEqual(
            audit["folds"]["2"]["records_with_no_seen_acceptable_target"],
            1,
        )
        self.assertEqual(audit["folds"]["2"]["closed_set_oracle_ceiling"], 0.0)
        self.assertEqual(audit["pooled"]["closed_set_oracle_ceiling"], 0.666666666667)

    def test_sequence_length_summary_contains_counts_not_target_values(self) -> None:
        secret_a = '["SECRET_A","SECRET_B"]'
        secret_b = '["SECRET_C"]'
        rows = [
            self._row("p0", "g0", 0, function=(secret_a,)),
            self._row("p1", "g1", 1, function=(secret_a,)),
            self._row("p2", "g2", 2, function=(secret_b,)),
        ]
        audit = _audit_specialist(rows, "FUNCTION_SPECIALIST")
        encoded = json.dumps(audit, sort_keys=True)
        self.assertNotIn("SECRET_A", encoded)
        self.assertNotIn("SECRET_B", encoded)
        self.assertNotIn("SECRET_C", encoded)
        self.assertEqual(audit["sequence_length"]["min"], 1)
        self.assertEqual(audit["sequence_length"]["max"], 2)
        self.assertEqual(audit["sequence_length"]["median"], 2.0)

    def test_scalar_key_targets_are_a_control_case(self) -> None:
        rows = [
            self._row("p0", "g0", 0, key=("C:",)),
            self._row("p1", "g1", 1, key=("C:",)),
            self._row("p2", "g2", 2, key=("G:",)),
        ]
        audit = _audit_specialist(rows, "KEY_SPECIALIST")
        self.assertEqual(audit["sequence_length"]["min"], 1)
        self.assertEqual(audit["sequence_length"]["max"], 1)
        self.assertEqual(audit["unique_target_count"], 2)

    def test_work_family_leakage_fails_closed(self) -> None:
        rows = [
            self._row("p0", "shared", 0, roman=('["I"]',)),
            self._row("p1", "shared", 1, roman=('["I"]',)),
            self._row("p2", "g2", 2, roman=('["V"]',)),
        ]
        with self.assertRaises(Stage2DTargetLearnabilityError):
            _audit_specialist(rows, "ROMAN_NUMERAL_SPECIALIST")

    def test_direct_cli_help_bootstraps_repository_imports(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            [
                sys.executable,
                str(repo_root / "scripts" / "run_stage2d_target_learnability_audit.py"),
                "--help",
            ],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("TRAIN-only specialist target learnability", completed.stdout)


if __name__ == "__main__":
    unittest.main()
