"""Stage 2-O cross-repository runtime-frame identity preflight.

Audit-only. Reproduces the engine Stage 2-N identity algorithm independently and
records whether the training repository can yet materialize exact engine-equivalent
runtime frames from TAVERN score sources. No model feature materialization or fit.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
from typing import Any

CONTRACT_SCHEMA = "st-stage2o-runtime-frame-identity-preflight-contract-v1"
SUMMARY_SCHEMA = "st-stage2o-runtime-frame-identity-preflight-summary-v1"
SOURCE_CORPUS = "TAVERN_REVIEWED_694"
EXPECTED_TRAINING_BASE_SHA = "0bcac2a6766a7bb50313973c1f4da524017d5263"
EXPECTED_ENGINE_STAGE2N_SHA = "f631ec8c30df616b9d83d9269e56278742878d32"
EXPECTED_STAGE2G_MANIFEST = "d7bbd514ec85b87aee423cae9dce39c74e634ab2f1040fed82af0e25105f255d"
EXPECTED_EVENT_COUNT = 1854
EXPECTED_SOURCE_PATH_COUNT = 363
ENGINE_IDENTITY_SCHEMA_NAME = "st_guitar_harmonic_engine.runtime_frame_identity"
ENGINE_IDENTITY_SCHEMA_VERSION = "1.0"
ENGINE_IDENTITY_PREFIX = "st-rfi-v1:"
FROZEN_SOURCE_SHA256 = "a" * 64
FROZEN_VECTOR = (
    "st-rfi-v1:bf32699f237452f333a7f2132842a893ad5212728abc4840fbb43f1ea6b5cc43"
)
ALLOWED_TIES = frozenset({"none", "start", "continue", "stop"})

REFERENCE_FRAME: dict[str, object] = {
    "measure_number": 1,
    "start": {"numerator": 0, "denominator": 1},
    "end": {"numerator": 1, "denominator": 1},
    "events": [
        {
            "measure_number": 1,
            "staff": 1,
            "voice": 1,
            "midi_pitch": 60,
            "onset": {"numerator": 0, "denominator": 1},
            "duration": {"numerator": 2, "denominator": 1},
            "tie": "none",
        },
        {
            "measure_number": 1,
            "staff": 1,
            "voice": 2,
            "midi_pitch": 64,
            "onset": {"numerator": 0, "denominator": 1},
            "duration": {"numerator": 2, "denominator": 1},
            "tie": "none",
        },
    ],
}


class Stage2ORuntimeFrameIdentityError(ValueError):
    pass


def _normalize_sha256(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    normalized = value.lower()
    if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
        raise Stage2ORuntimeFrameIdentityError(f"{name} must be exactly 64 hexadecimal characters")
    return normalized


def _int(value: object, *, name: str, minimum: int | None = None, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise Stage2ORuntimeFrameIdentityError(f"{name} must be an int")
    if minimum is not None and value < minimum:
        raise Stage2ORuntimeFrameIdentityError(f"{name} is below supported range")
    if maximum is not None and value > maximum:
        raise Stage2ORuntimeFrameIdentityError(f"{name} is above supported range")
    return value


def _rational(value: object, *, name: str) -> dict[str, int]:
    if not isinstance(value, dict) or set(value) != {"numerator", "denominator"}:
        raise Stage2ORuntimeFrameIdentityError(f"{name} must be an exact rational object")
    numerator = _int(value["numerator"], name=f"{name}.numerator")
    denominator = _int(value["denominator"], name=f"{name}.denominator", minimum=1)
    reduced = Fraction(numerator, denominator)
    return {"numerator": reduced.numerator, "denominator": reduced.denominator}


def _event_payload(value: object, *, frame_measure_number: int) -> dict[str, Any]:
    expected = {
        "measure_number",
        "staff",
        "voice",
        "midi_pitch",
        "onset",
        "duration",
        "tie",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise Stage2ORuntimeFrameIdentityError("event fields do not match Stage 2-N identity contract")
    measure_number = _int(value["measure_number"], name="event.measure_number", minimum=1)
    if measure_number != frame_measure_number:
        raise Stage2ORuntimeFrameIdentityError("event measure_number differs from frame")
    staff = _int(value["staff"], name="event.staff", minimum=1)
    voice = _int(value["voice"], name="event.voice", minimum=1)
    midi_pitch = _int(value["midi_pitch"], name="event.midi_pitch", minimum=0, maximum=127)
    onset = _rational(value["onset"], name="event.onset")
    duration = _rational(value["duration"], name="event.duration")
    if Fraction(onset["numerator"], onset["denominator"]) < 0:
        raise Stage2ORuntimeFrameIdentityError("event onset must not be negative")
    if Fraction(duration["numerator"], duration["denominator"]) <= 0:
        raise Stage2ORuntimeFrameIdentityError("event duration must be positive")
    tie = value["tie"]
    if not isinstance(tie, str) or tie not in ALLOWED_TIES:
        raise Stage2ORuntimeFrameIdentityError("event tie is unsupported")
    return {
        "measure_number": measure_number,
        "staff": staff,
        "voice": voice,
        "midi_pitch": midi_pitch,
        "onset": onset,
        "duration": duration,
        "tie": tie,
    }


def _event_sort_key(payload: dict[str, Any]) -> tuple[object, ...]:
    return (
        payload["measure_number"],
        payload["staff"],
        payload["voice"],
        payload["midi_pitch"],
        payload["onset"]["numerator"],
        payload["onset"]["denominator"],
        payload["duration"]["numerator"],
        payload["duration"]["denominator"],
        payload["tie"],
    )


def canonical_runtime_frame_identity_payload(frame: object, *, source_sha256: str) -> dict[str, Any]:
    if not isinstance(frame, dict) or set(frame) != {"measure_number", "start", "end", "events"}:
        raise Stage2ORuntimeFrameIdentityError("frame fields do not match Stage 2-N identity contract")
    source_sha256 = _normalize_sha256(source_sha256, name="source_sha256")
    measure_number = _int(frame["measure_number"], name="frame.measure_number", minimum=1)
    start = _rational(frame["start"], name="frame.start")
    end = _rational(frame["end"], name="frame.end")
    start_fraction = Fraction(start["numerator"], start["denominator"])
    end_fraction = Fraction(end["numerator"], end["denominator"])
    if start_fraction < 0 or end_fraction <= start_fraction:
        raise Stage2ORuntimeFrameIdentityError("frame boundaries are invalid")
    raw_events = frame["events"]
    if not isinstance(raw_events, list) or not raw_events:
        raise Stage2ORuntimeFrameIdentityError("frame events must be a non-empty list")
    events = [_event_payload(item, frame_measure_number=measure_number) for item in raw_events]
    for event in events:
        onset = Fraction(event["onset"]["numerator"], event["onset"]["denominator"])
        duration = Fraction(event["duration"]["numerator"], event["duration"]["denominator"])
        if onset > start_fraction or onset + duration < end_fraction:
            raise Stage2ORuntimeFrameIdentityError("event is not active across the whole frame")
    events.sort(key=_event_sort_key)
    return {
        "schema_name": ENGINE_IDENTITY_SCHEMA_NAME,
        "schema_version": ENGINE_IDENTITY_SCHEMA_VERSION,
        "source_sha256": source_sha256,
        "frame": {
            "measure_number": measure_number,
            "start": start,
            "end": end,
            "events": events,
        },
    }


def runtime_frame_id_from_primitives(frame: object, *, source_sha256: str) -> str:
    payload = canonical_runtime_frame_identity_payload(frame, source_sha256=source_sha256)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return ENGINE_IDENTITY_PREFIX + hashlib.sha256(encoded).hexdigest()


def engine_identity_vector_reproduced() -> bool:
    return runtime_frame_id_from_primitives(REFERENCE_FRAME, source_sha256=FROZEN_SOURCE_SHA256) == FROZEN_VECTOR


@dataclass(frozen=True, slots=True)
class SourceMaterializerEvidence:
    engine_stage2n_sha: str
    stage2g_manifest_sha256: str
    stage2g_event_count: int
    stage2g_source_path_count: int
    engine_identity_vector_reproduced: bool
    score_source_sha256_available: bool
    exact_runtime_measure_number_equivalence_established: bool
    exact_runtime_event_onset_materialization_established: bool
    exact_runtime_event_duration_materialization_established: bool
    exact_runtime_tie_state_materialization_established: bool
    exact_runtime_staff_voice_mapping_established: bool
    exact_harmonic_frame_segmentation_established: bool
    stage2g_event_to_runtime_frame_join_established: bool
    nearest_frame_matching_used: bool = False
    order_only_matching_used: bool = False
    inferred_onset_used: bool = False
    inferred_duration_used: bool = False
    harmonic_label_assisted_alignment_used: bool = False
    teacher_target_assisted_alignment_used: bool = False
    next_or_future_context_used: bool = False
    non_train_access: bool = False


def build_stage2o_contract() -> dict[str, object]:
    return {
        "schema_version": CONTRACT_SCHEMA,
        "stage": "STAGE_2_O",
        "audit_only": True,
        "source_training_main_sha": EXPECTED_TRAINING_BASE_SHA,
        "source_engine_repository": "khfy7wpr5p-maker/st-guitar-harmonic-engine",
        "source_engine_stage2n_main_sha": EXPECTED_ENGINE_STAGE2N_SHA,
        "source_stage2g_private_event_manifest_sha256": EXPECTED_STAGE2G_MANIFEST,
        "source_stage2g_materialized_event_count": EXPECTED_EVENT_COUNT,
        "source_stage2g_materializable_source_path_count": EXPECTED_SOURCE_PATH_COUNT,
        "source_corpus": SOURCE_CORPUS,
        "eligible_original_partition": "TRAIN",
        "target_shape": "FUNCTION_ONSET_EVENT",
        "engine_identity_schema_name": ENGINE_IDENTITY_SCHEMA_NAME,
        "engine_identity_schema_version": ENGINE_IDENTITY_SCHEMA_VERSION,
        "engine_identity_prefix": ENGINE_IDENTITY_PREFIX,
        "frozen_cross_repo_identity_vector": FROZEN_VECTOR,
        "identity_role": "JOIN_KEY_NOT_MODEL_FEATURE",
        "model_feature_materialization_authorized": False,
        "model_training_started": False,
        "model_selection_started": False,
        "non_train_access_authorized": False,
        "production_authority": False,
        "deterministic_resolver_remains_authoritative": True,
    }


def audit_source_materializer_evidence(evidence: SourceMaterializerEvidence) -> dict[str, object]:
    if evidence.engine_stage2n_sha != EXPECTED_ENGINE_STAGE2N_SHA:
        raise Stage2ORuntimeFrameIdentityError("engine Stage 2-N SHA pin mismatch")
    if evidence.stage2g_manifest_sha256 != EXPECTED_STAGE2G_MANIFEST:
        raise Stage2ORuntimeFrameIdentityError("Stage 2-G private event manifest pin mismatch")
    if evidence.stage2g_event_count != EXPECTED_EVENT_COUNT:
        raise Stage2ORuntimeFrameIdentityError("Stage 2-G event count mismatch")
    if evidence.stage2g_source_path_count != EXPECTED_SOURCE_PATH_COUNT:
        raise Stage2ORuntimeFrameIdentityError("Stage 2-G source path count mismatch")
    if not engine_identity_vector_reproduced() or not evidence.engine_identity_vector_reproduced:
        raise Stage2ORuntimeFrameIdentityError("engine Stage 2-N frozen identity vector not reproduced")

    forbidden = {
        "nearest_frame_matching_used": evidence.nearest_frame_matching_used,
        "order_only_matching_used": evidence.order_only_matching_used,
        "inferred_onset_used": evidence.inferred_onset_used,
        "inferred_duration_used": evidence.inferred_duration_used,
        "harmonic_label_assisted_alignment_used": evidence.harmonic_label_assisted_alignment_used,
        "teacher_target_assisted_alignment_used": evidence.teacher_target_assisted_alignment_used,
        "next_or_future_context_used": evidence.next_or_future_context_used,
        "non_train_access": evidence.non_train_access,
    }
    violations = sorted(name for name, used in forbidden.items() if used)
    if violations:
        raise Stage2ORuntimeFrameIdentityError(f"forbidden Stage 2-O mechanism used: {violations}")

    required = {
        "score_source_sha256_available": evidence.score_source_sha256_available,
        "exact_runtime_measure_number_equivalence_established": evidence.exact_runtime_measure_number_equivalence_established,
        "exact_runtime_event_onset_materialization_established": evidence.exact_runtime_event_onset_materialization_established,
        "exact_runtime_event_duration_materialization_established": evidence.exact_runtime_event_duration_materialization_established,
        "exact_runtime_tie_state_materialization_established": evidence.exact_runtime_tie_state_materialization_established,
        "exact_runtime_staff_voice_mapping_established": evidence.exact_runtime_staff_voice_mapping_established,
        "exact_harmonic_frame_segmentation_established": evidence.exact_harmonic_frame_segmentation_established,
        "stage2g_event_to_runtime_frame_join_established": evidence.stage2g_event_to_runtime_frame_join_established,
    }
    missing = sorted(name for name, available in required.items() if not available)
    exact_alignment_ready = not missing
    return {
        "schema_version": SUMMARY_SCHEMA,
        "source_corpus": SOURCE_CORPUS,
        "eligible_original_partition": "TRAIN",
        "source_engine_stage2n_main_sha": evidence.engine_stage2n_sha,
        "source_stage2g_private_event_manifest_sha256": evidence.stage2g_manifest_sha256,
        "source_stage2g_materialized_event_count": evidence.stage2g_event_count,
        "source_stage2g_materializable_source_path_count": evidence.stage2g_source_path_count,
        "engine_identity_vector_reproduced": True,
        "frozen_cross_repo_identity_vector": FROZEN_VECTOR,
        "required_source_materializer_evidence_missing": missing,
        "exact_stage2g_event_to_runtime_frame_alignment_ready": exact_alignment_ready,
        "model_feature_materialization_authorized": False,
        "model_training_started": False,
        "model_selection_started": False,
        "non_train_access": False,
        "production_authority": False,
        "deterministic_resolver_remains_authoritative": True,
        "decision": (
            "EXACT_RUNTIME_FRAME_IDENTITY_READY_FOR_PRIVATE_JOIN_AUDIT"
            if exact_alignment_ready
            else "ENGINE_IDENTITY_REPRODUCED_EXACT_KERN_RUNTIME_FRAME_MATERIALIZER_REQUIRED"
        ),
    }


def current_repository_reality_summary() -> dict[str, object]:
    """Encode current repository reality without pretending exact **kern timing exists."""
    return audit_source_materializer_evidence(
        SourceMaterializerEvidence(
            engine_stage2n_sha=EXPECTED_ENGINE_STAGE2N_SHA,
            stage2g_manifest_sha256=EXPECTED_STAGE2G_MANIFEST,
            stage2g_event_count=EXPECTED_EVENT_COUNT,
            stage2g_source_path_count=EXPECTED_SOURCE_PATH_COUNT,
            engine_identity_vector_reproduced=engine_identity_vector_reproduced(),
            score_source_sha256_available=True,
            exact_runtime_measure_number_equivalence_established=False,
            exact_runtime_event_onset_materialization_established=False,
            exact_runtime_event_duration_materialization_established=False,
            exact_runtime_tie_state_materialization_established=False,
            exact_runtime_staff_voice_mapping_established=False,
            exact_harmonic_frame_segmentation_established=False,
            stage2g_event_to_runtime_frame_join_established=False,
        )
    )
