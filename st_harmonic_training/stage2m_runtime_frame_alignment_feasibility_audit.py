"""Stage 2-M exact event-to-runtime-frame alignment feasibility audit.

Audit-only. It never materializes model features, never fits a model, and never
recovers missing timing or alignment with heuristics. Exact source-grounded
identity is required before Function training can advance.
"""
from __future__ import annotations

from dataclasses import dataclass

EXPECTED_ENGINE_SHA = "eef494d381a308200f502332db85091697bab163"
EXPECTED_STAGE2G_MANIFEST = "d7bbd514ec85b87aee423cae9dce39c74e634ab2f1040fed82af0e25105f255d"
EXPECTED_EVENT_COUNT = 1854
EXPECTED_SOURCE_PATH_COUNT = 363


@dataclass(frozen=True, slots=True)
class AlignmentEvidence:
    stage2g_manifest_sha256: str
    stage2g_event_count: int
    stage2g_source_path_count: int
    engine_sha: str
    runtime_frame_export_contract_established: bool
    source_path_identity_available: bool
    exact_event_to_frame_identity_available: bool
    current_pitch_class_mask_available: bool
    current_bass_pc_available: bool
    current_note_count_available: bool
    previous_frame_reference_available: bool
    inferred_timing_used: bool = False
    inferred_duration_used: bool = False
    inferred_segment_boundary_used: bool = False
    next_or_future_context_used: bool = False
    teacher_gold_function_used_as_feature: bool = False
    tavern_harmonic_token_used_as_runtime_feature: bool = False
    joined_harmonic_label_used_as_authority: bool = False
    ai_generated_alignment_used: bool = False
    heuristic_recovery_used: bool = False


def audit(evidence: AlignmentEvidence) -> dict:
    if evidence.stage2g_manifest_sha256 != EXPECTED_STAGE2G_MANIFEST:
        raise ValueError("Stage 2-G private event manifest pin mismatch")
    if evidence.stage2g_event_count != EXPECTED_EVENT_COUNT:
        raise ValueError("Stage 2-G event count mismatch")
    if evidence.stage2g_source_path_count != EXPECTED_SOURCE_PATH_COUNT:
        raise ValueError("Stage 2-G source path count mismatch")
    if evidence.engine_sha != EXPECTED_ENGINE_SHA:
        raise ValueError("engine SHA pin mismatch")

    forbidden = {
        "inferred_timing_used": evidence.inferred_timing_used,
        "inferred_duration_used": evidence.inferred_duration_used,
        "inferred_segment_boundary_used": evidence.inferred_segment_boundary_used,
        "next_or_future_context_used": evidence.next_or_future_context_used,
        "teacher_gold_function_used_as_feature": evidence.teacher_gold_function_used_as_feature,
        "tavern_harmonic_token_used_as_runtime_feature": evidence.tavern_harmonic_token_used_as_runtime_feature,
        "joined_harmonic_label_used_as_authority": evidence.joined_harmonic_label_used_as_authority,
        "ai_generated_alignment_used": evidence.ai_generated_alignment_used,
        "heuristic_recovery_used": evidence.heuristic_recovery_used,
    }
    violations = sorted(name for name, used in forbidden.items() if used)
    if violations:
        raise ValueError(f"forbidden alignment mechanism used: {violations}")

    required = {
        "runtime_frame_export_contract_established": evidence.runtime_frame_export_contract_established,
        "source_path_identity_available": evidence.source_path_identity_available,
        "exact_event_to_frame_identity_available": evidence.exact_event_to_frame_identity_available,
        "current_pitch_class_mask_available": evidence.current_pitch_class_mask_available,
        "current_bass_pc_available": evidence.current_bass_pc_available,
        "current_note_count_available": evidence.current_note_count_available,
    }
    missing = sorted(name for name, available in required.items() if not available)
    established = not missing

    return {
        "schema_version": "st-stage2m-runtime-frame-alignment-feasibility-audit-summary-v1",
        "engine_sha": evidence.engine_sha,
        "stage2g_private_event_manifest_sha256": evidence.stage2g_manifest_sha256,
        "stage2g_event_count": evidence.stage2g_event_count,
        "stage2g_source_path_count": evidence.stage2g_source_path_count,
        "required_evidence_missing": missing,
        "exact_event_to_runtime_frame_alignment_established": established,
        "previous_frame_reference_available": evidence.previous_frame_reference_available,
        "feature_materialization_authorized": False,
        "model_training_started": False,
        "model_selection_started": False,
        "non_train_access": False,
        "production_authority": False,
        "deterministic_resolver_remains_authoritative": True,
        "decision": (
            "EXACT_ALIGNMENT_FEASIBLE_BUT_FEATURE_MATERIALIZATION_STILL_CLOSED"
            if established
            else "HOLD_UNTIL_EXACT_RUNTIME_FRAME_EXPORT_AND_IDENTITY_BRIDGE_EXIST"
        ),
    }


def current_repository_reality_summary() -> dict:
    """Encode the known Stage 2-L/2-G reality without inventing missing runtime data."""
    return audit(
        AlignmentEvidence(
            stage2g_manifest_sha256=EXPECTED_STAGE2G_MANIFEST,
            stage2g_event_count=EXPECTED_EVENT_COUNT,
            stage2g_source_path_count=EXPECTED_SOURCE_PATH_COUNT,
            engine_sha=EXPECTED_ENGINE_SHA,
            runtime_frame_export_contract_established=False,
            source_path_identity_available=True,
            exact_event_to_frame_identity_available=False,
            current_pitch_class_mask_available=False,
            current_bass_pc_available=False,
            current_note_count_available=False,
            previous_frame_reference_available=False,
        )
    )
