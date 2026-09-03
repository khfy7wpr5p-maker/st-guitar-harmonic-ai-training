import unittest

from st_harmonic_training.stage2m_runtime_frame_alignment_feasibility_audit import (
    AlignmentEvidence,
    EXPECTED_ENGINE_SHA,
    EXPECTED_EVENT_COUNT,
    EXPECTED_SOURCE_PATH_COUNT,
    EXPECTED_STAGE2G_MANIFEST,
    audit,
    current_repository_reality_summary,
)


class Stage2MRuntimeFrameAlignmentFeasibilityAuditTests(unittest.TestCase):
    def base(self, **changes):
        values = dict(
            stage2g_manifest_sha256=EXPECTED_STAGE2G_MANIFEST,
            stage2g_event_count=EXPECTED_EVENT_COUNT,
            stage2g_source_path_count=EXPECTED_SOURCE_PATH_COUNT,
            engine_sha=EXPECTED_ENGINE_SHA,
            runtime_frame_export_contract_established=True,
            source_path_identity_available=True,
            exact_event_to_frame_identity_available=True,
            current_pitch_class_mask_available=True,
            current_bass_pc_available=True,
            current_note_count_available=True,
            previous_frame_reference_available=True,
        )
        values.update(changes)
        return AlignmentEvidence(**values)

    def test_exact_evidence_can_establish_feasibility_without_training_authority(self):
        summary = audit(self.base())
        self.assertTrue(summary["exact_event_to_runtime_frame_alignment_established"])
        self.assertFalse(summary["feature_materialization_authorized"])
        self.assertFalse(summary["model_training_started"])
        self.assertFalse(summary["production_authority"])

    def test_current_repository_reality_remains_hold(self):
        summary = current_repository_reality_summary()
        self.assertFalse(summary["exact_event_to_runtime_frame_alignment_established"])
        self.assertIn("runtime_frame_export_contract_established", summary["required_evidence_missing"])
        self.assertEqual(
            summary["decision"],
            "HOLD_UNTIL_EXACT_RUNTIME_FRAME_EXPORT_AND_IDENTITY_BRIDGE_EXIST",
        )

    def test_previous_frame_reference_is_not_required_for_current_frame_alignment(self):
        summary = audit(self.base(previous_frame_reference_available=False))
        self.assertTrue(summary["exact_event_to_runtime_frame_alignment_established"])
        self.assertFalse(summary["previous_frame_reference_available"])

    def test_manifest_pin_mismatch_fails_closed(self):
        with self.assertRaises(ValueError):
            audit(self.base(stage2g_manifest_sha256="bad"))

    def test_event_count_mismatch_fails_closed(self):
        with self.assertRaises(ValueError):
            audit(self.base(stage2g_event_count=1))

    def test_source_path_count_mismatch_fails_closed(self):
        with self.assertRaises(ValueError):
            audit(self.base(stage2g_source_path_count=1))

    def test_engine_pin_mismatch_fails_closed(self):
        with self.assertRaises(ValueError):
            audit(self.base(engine_sha="bad"))

    def test_missing_exact_identity_holds(self):
        summary = audit(self.base(exact_event_to_frame_identity_available=False))
        self.assertFalse(summary["exact_event_to_runtime_frame_alignment_established"])

    def test_missing_current_frame_feature_holds(self):
        summary = audit(self.base(current_pitch_class_mask_available=False))
        self.assertFalse(summary["exact_event_to_runtime_frame_alignment_established"])

    def test_all_forbidden_mechanisms_fail_closed(self):
        forbidden = (
            "inferred_timing_used",
            "inferred_duration_used",
            "inferred_segment_boundary_used",
            "next_or_future_context_used",
            "teacher_gold_function_used_as_feature",
            "tavern_harmonic_token_used_as_runtime_feature",
            "joined_harmonic_label_used_as_authority",
            "ai_generated_alignment_used",
            "heuristic_recovery_used",
        )
        for field in forbidden:
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    audit(self.base(**{field: True}))


if __name__ == "__main__":
    unittest.main()
