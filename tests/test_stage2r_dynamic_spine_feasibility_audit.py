from __future__ import annotations

import unittest

from st_harmonic_training.stage2r_dynamic_spine_feasibility_audit import (
    Stage2RDynamicSpineAuditError,
    build_stage2r_contract,
    scan_spine_topology,
    validate_stage2r_contract,
)


STATIC_SCORE = """**kern\t**kern
*staff2\t*staff1
=1\t=1
4C\t4c
*-\t*-
"""

SPLIT_JOIN_SCORE = """**kern\t**kern
*staff2\t*staff1
*\t*^
4C\t4c\t4e
*\t*v\t*v
2G\t2d
*-\t*-
"""

SPLIT_JOIN_JOINED = """**function\t**harm\t**kern\t**kern
*\t*\t*\t*
*\t*\t*\t*^
T\t4I\t4C\t4c\t4e
*\t*\t*\t*v\t*v
D\t2V\t2G\t2d
*-\t*-\t*-\t*-
"""


class Stage2RDynamicSpineFeasibilityAuditTests(unittest.TestCase):
    def test_contract_is_audit_only(self):
        contract = validate_stage2r_contract(build_stage2r_contract())
        self.assertTrue(contract["audit_only"])
        self.assertFalse(contract["dynamic_spine_materialization_authorized"])
        self.assertFalse(contract["timing_inference_authorized"])
        self.assertFalse(contract["function_target_value_access_for_topology"])
        self.assertFalse(contract["joined_harmonic_label_value_access_for_topology"])
        self.assertFalse(contract["model_feature_materialization_authorized"])
        self.assertFalse(contract["model_training_started"])
        self.assertFalse(contract["production_authority"])
        self.assertTrue(contract["deterministic_resolver_remains_authoritative"])

    def test_static_score_has_no_dynamic_topology(self):
        result = scan_spine_topology(STATIC_SCORE, source_kind="SCORE")
        self.assertEqual(result["initial_kern_spine_count"], 2)
        self.assertEqual(result["max_observed_kern_spine_count"], 2)
        self.assertFalse(result["dynamic_path_present"])
        self.assertEqual(result["operation_occurrences"], {"*^": 0, "*v": 0, "*x": 0, "*+": 0})

    def test_score_split_join_is_counted_without_materializing_music(self):
        result = scan_spine_topology(SPLIT_JOIN_SCORE, source_kind="SCORE")
        self.assertTrue(result["dynamic_path_present"])
        self.assertTrue(result["split_present"])
        self.assertTrue(result["join_present"])
        self.assertFalse(result["exchange_present"])
        self.assertFalse(result["add_present"])
        self.assertEqual(result["initial_kern_spine_count"], 2)
        self.assertEqual(result["max_observed_kern_spine_count"], 3)
        self.assertEqual(result["operation_occurrences"]["*^"], 1)
        self.assertEqual(result["operation_occurrences"]["*v"], 2)

    def test_joined_fixed_non_kern_columns_are_excluded_from_max_kern_count(self):
        result = scan_spine_topology(SPLIT_JOIN_JOINED, source_kind="JOINED")
        self.assertEqual(result["initial_kern_spine_count"], 2)
        self.assertEqual(result["max_observed_kern_spine_count"], 3)
        self.assertEqual(result["max_row_width"], 5)
        self.assertTrue(result["split_present"])
        self.assertTrue(result["join_present"])

    def test_exchange_and_add_are_visible_not_silently_ignored(self):
        exchange = "**kern\t**kern\n*x\t*x\n4C\t4c\n*-\t*-\n"
        result = scan_spine_topology(exchange, source_kind="SCORE")
        self.assertTrue(result["exchange_present"])
        self.assertEqual(result["operation_occurrences"]["*x"], 2)

        add = "**kern\t**kern\n*+\t*\n4C\t4c\t4e\n*-\t*-\t*-\n"
        result = scan_spine_topology(add, source_kind="SCORE")
        self.assertTrue(result["add_present"])
        self.assertEqual(result["operation_occurrences"]["*+"], 1)

    def test_unknown_source_kind_fails_closed(self):
        with self.assertRaises(Stage2RDynamicSpineAuditError):
            scan_spine_topology(STATIC_SCORE, source_kind="OTHER")

    def test_score_with_non_kern_header_fails_closed(self):
        with self.assertRaises(Stage2RDynamicSpineAuditError):
            scan_spine_topology("**kern\t**harm\n4C\t4I\n*-\t*-\n", source_kind="SCORE")

    def test_joined_with_unknown_spine_type_fails_closed(self):
        bad = "**function\t**harm\t**kern\t**foo\nT\t4I\t4C\tx\n*-\t*-\t*-\t*-\n"
        with self.assertRaises(Stage2RDynamicSpineAuditError):
            scan_spine_topology(bad, source_kind="JOINED")


if __name__ == "__main__":
    unittest.main()
