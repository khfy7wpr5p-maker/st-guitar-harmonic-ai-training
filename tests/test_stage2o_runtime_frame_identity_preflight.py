import copy
import unittest

from st_harmonic_training.stage2o_runtime_frame_identity_preflight import (
    EXPECTED_ENGINE_STAGE2N_SHA,
    EXPECTED_EVENT_COUNT,
    EXPECTED_SOURCE_PATH_COUNT,
    EXPECTED_STAGE2G_MANIFEST,
    FROZEN_SOURCE_SHA256,
    FROZEN_VECTOR,
    REFERENCE_FRAME,
    SourceMaterializerEvidence,
    Stage2ORuntimeFrameIdentityError,
    audit_source_materializer_evidence,
    build_stage2o_contract,
    current_repository_reality_summary,
    engine_identity_vector_reproduced,
    runtime_frame_id_from_primitives,
)


class Stage2ORuntimeFrameIdentityPreflightTests(unittest.TestCase):
    def _all_ready(self, **overrides):
        data = dict(
            engine_stage2n_sha=EXPECTED_ENGINE_STAGE2N_SHA,
            stage2g_manifest_sha256=EXPECTED_STAGE2G_MANIFEST,
            stage2g_event_count=EXPECTED_EVENT_COUNT,
            stage2g_source_path_count=EXPECTED_SOURCE_PATH_COUNT,
            engine_identity_vector_reproduced=True,
            score_source_sha256_available=True,
            exact_runtime_measure_number_equivalence_established=True,
            exact_runtime_event_onset_materialization_established=True,
            exact_runtime_event_duration_materialization_established=True,
            exact_runtime_tie_state_materialization_established=True,
            exact_runtime_staff_voice_mapping_established=True,
            exact_harmonic_frame_segmentation_established=True,
            stage2g_event_to_runtime_frame_join_established=True,
        )
        data.update(overrides)
        return SourceMaterializerEvidence(**data)

    def test_frozen_engine_vector_is_reproduced(self):
        self.assertTrue(engine_identity_vector_reproduced())
        self.assertEqual(
            runtime_frame_id_from_primitives(
                REFERENCE_FRAME, source_sha256=FROZEN_SOURCE_SHA256
            ),
            FROZEN_VECTOR,
        )

    def test_event_order_is_canonicalized(self):
        reversed_frame = copy.deepcopy(REFERENCE_FRAME)
        reversed_frame["events"] = list(reversed(reversed_frame["events"]))
        self.assertEqual(
            runtime_frame_id_from_primitives(
                reversed_frame, source_sha256=FROZEN_SOURCE_SHA256
            ),
            FROZEN_VECTOR,
        )

    def test_rationals_are_reduced_like_engine(self):
        frame = copy.deepcopy(REFERENCE_FRAME)
        frame["end"] = {"numerator": 2, "denominator": 2}
        self.assertEqual(
            runtime_frame_id_from_primitives(frame, source_sha256=FROZEN_SOURCE_SHA256),
            FROZEN_VECTOR,
        )

    def test_source_digest_scopes_identity(self):
        other = runtime_frame_id_from_primitives(REFERENCE_FRAME, source_sha256="b" * 64)
        self.assertNotEqual(other, FROZEN_VECTOR)

    def test_invalid_source_digest_fails_closed(self):
        with self.assertRaises(Stage2ORuntimeFrameIdentityError):
            runtime_frame_id_from_primitives(REFERENCE_FRAME, source_sha256="x" * 64)

    def test_invalid_frame_boundary_fails_closed(self):
        frame = copy.deepcopy(REFERENCE_FRAME)
        frame["end"] = {"numerator": 0, "denominator": 1}
        with self.assertRaises(Stage2ORuntimeFrameIdentityError):
            runtime_frame_id_from_primitives(frame, source_sha256=FROZEN_SOURCE_SHA256)

    def test_inactive_event_fails_closed(self):
        frame = copy.deepcopy(REFERENCE_FRAME)
        frame["events"][0]["onset"] = {"numerator": 1, "denominator": 1}
        with self.assertRaises(Stage2ORuntimeFrameIdentityError):
            runtime_frame_id_from_primitives(frame, source_sha256=FROZEN_SOURCE_SHA256)

    def test_contract_keeps_training_closed(self):
        contract = build_stage2o_contract()
        self.assertTrue(contract["audit_only"])
        self.assertEqual(contract["identity_role"], "JOIN_KEY_NOT_MODEL_FEATURE")
        self.assertFalse(contract["model_feature_materialization_authorized"])
        self.assertFalse(contract["model_training_started"])
        self.assertFalse(contract["production_authority"])

    def test_current_reality_is_hold_on_exact_source_materializer(self):
        summary = current_repository_reality_summary()
        self.assertTrue(summary["engine_identity_vector_reproduced"])
        self.assertFalse(summary["exact_stage2g_event_to_runtime_frame_alignment_ready"])
        self.assertIn(
            "exact_runtime_event_onset_materialization_established",
            summary["required_source_materializer_evidence_missing"],
        )
        self.assertEqual(
            summary["decision"],
            "ENGINE_IDENTITY_REPRODUCED_EXACT_KERN_RUNTIME_FRAME_MATERIALIZER_REQUIRED",
        )

    def test_all_exact_evidence_marks_join_audit_ready_without_starting_training(self):
        summary = audit_source_materializer_evidence(self._all_ready())
        self.assertTrue(summary["exact_stage2g_event_to_runtime_frame_alignment_ready"])
        self.assertEqual(
            summary["decision"], "EXACT_RUNTIME_FRAME_IDENTITY_READY_FOR_PRIVATE_JOIN_AUDIT"
        )
        self.assertFalse(summary["model_feature_materialization_authorized"])
        self.assertFalse(summary["model_training_started"])
        self.assertFalse(summary["production_authority"])

    def test_forbidden_heuristic_alignment_fails_closed(self):
        for field in (
            "nearest_frame_matching_used",
            "order_only_matching_used",
            "inferred_onset_used",
            "inferred_duration_used",
            "harmonic_label_assisted_alignment_used",
            "teacher_target_assisted_alignment_used",
            "next_or_future_context_used",
            "non_train_access",
        ):
            with self.subTest(field=field):
                with self.assertRaises(Stage2ORuntimeFrameIdentityError):
                    audit_source_materializer_evidence(self._all_ready(**{field: True}))

    def test_pins_fail_closed(self):
        with self.assertRaises(Stage2ORuntimeFrameIdentityError):
            audit_source_materializer_evidence(self._all_ready(engine_stage2n_sha="0" * 40))
        with self.assertRaises(Stage2ORuntimeFrameIdentityError):
            audit_source_materializer_evidence(self._all_ready(stage2g_manifest_sha256="0" * 64))


if __name__ == "__main__":
    unittest.main()
