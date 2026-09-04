"""Stage 2-Q TRAIN-only exact Stage2G event -> runtime-frame coverage audit.

This audit consumes the private Stage2G Function-onset payload plus the pinned
TAVERN archive. It never fits a model and never recovers missing alignment with
nearest-frame, order-only, inferred timing, or target-label heuristics.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import zipfile
from typing import Any

from .offline_experiment import require_locked_runtime
from .safe_ingest import load_bounded_json
from .stage1e_internal_cv import FOLD_COUNT
from .stage2h_function_event_cv import (
    EXPECTED_STAGE2G_EVENT_COUNT,
    EXPECTED_STAGE2G_MATERIALIZABLE_SOURCE_PATH_COUNT,
    EXPECTED_STAGE2G_PRIVATE_EVENT_MANIFEST_SHA256,
    MAX_PRIVATE_BYTES,
    _validate_stage2g_private_payload,
)
from .stage2o_runtime_frame_identity_preflight import (
    EXPECTED_ENGINE_STAGE2N_SHA,
    canonical_runtime_frame_identity_payload,
)
from .stage2p_exact_kern_runtime_frame_materializer import (
    DURATION_RE,
    MATERIALIZER_VERSION,
    MAX_KERN_SPINES,
    MAX_LINES,
    MAX_SOURCE_BYTES,
    SPINE_PATH_TOKENS,
    STAFF_RE,
    Stage2PExactKernMaterializerError,
    _frames_for_measure,
    _parse_cell,
    _reciprocal_to_quarter_length,
    materialize_exact_kern_runtime_frames,
)
from .tavern_event_alignment_audit import _joined_member
from .tavern_raw_label_realization import (
    MAX_ARCHIVE_BYTES,
    PINNED_TAVERN_ARCHIVE_SHA256,
    _bounded_regular_file,
    _validated_zip_members,
)
from .tavern_score_input_realization import MAX_SCORE_BYTES, _archive_root, _score_member

CONTRACT_SCHEMA = "st-stage2q-exact-runtime-alignment-coverage-contract-v1"
SUMMARY_SCHEMA = "st-stage2q-exact-runtime-alignment-coverage-summary-v1"
SOURCE_CORPUS = "TAVERN_REVIEWED_694"
EXPECTED_TRAINING_BASE_SHA = "8e35d18ef2ce3a4bb819aef9f239cbc9877e7984"
JOINED_TIMING_POLICY = "STATIC_**KERN_PLUS_SINGLE_**HARM_EXACT_RHYTHMIC_CLOCK"
FRAME_JOIN_POLICY = "EXACT_MEASURE_AND_FRAME_START_ONLY"


class Stage2QExactRuntimeAlignmentError(ValueError):
    pass


def build_stage2q_contract() -> dict[str, object]:
    return {
        "schema_version": CONTRACT_SCHEMA,
        "stage": "STAGE_2_Q",
        "audit_only": True,
        "source_training_main_sha": EXPECTED_TRAINING_BASE_SHA,
        "source_engine_stage2n_main_sha": EXPECTED_ENGINE_STAGE2N_SHA,
        "source_corpus": SOURCE_CORPUS,
        "eligible_original_partition": "TRAIN",
        "source_stage2g_private_event_manifest_sha256": EXPECTED_STAGE2G_PRIVATE_EVENT_MANIFEST_SHA256,
        "source_stage2g_materialized_event_count": EXPECTED_STAGE2G_EVENT_COUNT,
        "source_stage2g_materializable_source_path_count": EXPECTED_STAGE2G_MATERIALIZABLE_SOURCE_PATH_COUNT,
        "source_tavern_archive_sha256": PINNED_TAVERN_ARCHIVE_SHA256,
        "source_stage2p_materializer_version": MATERIALIZER_VERSION,
        "joined_timing_policy": JOINED_TIMING_POLICY,
        "frame_join_policy": FRAME_JOIN_POLICY,
        "joined_harmonic_label_text_used": False,
        "joined_harmonic_reciprocal_used_as_exact_timing_evidence": True,
        "teacher_function_token_used_for_alignment": False,
        "nearest_frame_matching_authorized": False,
        "order_only_matching_authorized": False,
        "inferred_onset_authorized": False,
        "inferred_duration_authorized": False,
        "next_or_future_context_authorized": False,
        "partial_alignment_auto_admission_authorized": False,
        "runtime_frame_id_role": "JOIN_KEY_NOT_MODEL_FEATURE",
        "model_feature_materialization_authorized": False,
        "model_training_started": False,
        "model_selection_started": False,
        "non_train_access_authorized": False,
        "production_authority": False,
        "deterministic_resolver_remains_authoritative": True,
    }


def validate_stage2q_contract(data: object) -> dict[str, object]:
    expected = build_stage2q_contract()
    if not isinstance(data, dict) or data != expected:
        raise Stage2QExactRuntimeAlignmentError("Stage 2-Q contract differs from frozen audit contract")
    return data


def _fraction_payload(value: Fraction) -> dict[str, int]:
    return {"numerator": value.numerator, "denominator": value.denominator}


def _payload_fraction(value: object) -> Fraction:
    if not isinstance(value, dict) or set(value) != {"numerator", "denominator"}:
        raise Stage2QExactRuntimeAlignmentError("malformed rational payload")
    numerator = value["numerator"]
    denominator = value["denominator"]
    if isinstance(numerator, bool) or not isinstance(numerator, int):
        raise Stage2QExactRuntimeAlignmentError("rational numerator must be int")
    if isinstance(denominator, bool) or not isinstance(denominator, int) or denominator <= 0:
        raise Stage2QExactRuntimeAlignmentError("rational denominator must be positive int")
    return Fraction(numerator, denominator)


def _harmonic_duration(token: str) -> Fraction:
    match = DURATION_RE.match(token)
    if match is None or not match.group("body"):
        raise Stage2QExactRuntimeAlignmentError("Joined harmonic event lacks explicit reciprocal")
    return _reciprocal_to_quarter_length(match.group("recip"), len(match.group("dots")))


def _is_data_token(token: str) -> bool:
    return bool(token) and not token.startswith(("*", "=", "!", "."))


def _canonical_frame(frame: object) -> dict[str, Any]:
    return canonical_runtime_frame_identity_payload(frame, source_sha256="0" * 64)["frame"]


def _materialize_joined_carrier_and_frames(raw_joined_bytes: bytes) -> dict[str, object]:
    """Materialize exact Joined **kern frames and **harm event positions.

    Only the static rhythmic subset is accepted. The **harm label body is never
    interpreted; only its explicit reciprocal participates in the shared exact
    rhythmic clock.
    """
    if not isinstance(raw_joined_bytes, bytes):
        raise TypeError("raw_joined_bytes must be bytes")
    if not raw_joined_bytes or len(raw_joined_bytes) > MAX_SOURCE_BYTES:
        raise Stage2QExactRuntimeAlignmentError("Joined source is empty or exceeds size bound")
    try:
        text = raw_joined_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise Stage2QExactRuntimeAlignmentError("Joined source is not strict UTF-8") from exc
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if len(lines) > MAX_LINES:
        raise Stage2QExactRuntimeAlignmentError("Joined line count exceeds bound")

    header_indices = [index for index, line in enumerate(lines) if line.startswith("**")]
    if len(header_indices) != 1:
        raise Stage2QExactRuntimeAlignmentError("Joined source must contain one exclusive header")
    header_index = header_indices[0]
    columns = lines[header_index].split("\t")
    kern_indices = [index for index, value in enumerate(columns) if value == "**kern"]
    harm_indices = [index for index, value in enumerate(columns) if value == "**harm"]
    if not kern_indices or len(kern_indices) > MAX_KERN_SPINES:
        raise Stage2QExactRuntimeAlignmentError("Joined source has unsupported **kern spine count")
    if len(harm_indices) != 1:
        raise Stage2QExactRuntimeAlignmentError("Joined source must contain exactly one **harm spine")
    if any(value not in {"**kern", "**harm"} for value in columns):
        raise Stage2QExactRuntimeAlignmentError("Joined exact timing audit rejects extra spine types")
    harm_index = harm_indices[0]
    kern_ordinal = {column_index: ordinal + 1 for ordinal, column_index in enumerate(kern_indices)}
    staffs: dict[int, int | None] = {column_index: None for column_index in kern_indices}
    remaining: dict[int, Fraction] = {column_index: Fraction(0) for column_index in kern_indices}
    remaining[harm_index] = Fraction(0)

    first_kern_data_seen = False
    measure_number = 1
    local_time = Fraction(0)
    measure_started = False
    measure_note_events: list[dict[str, object]] = []
    all_frames: list[dict[str, object]] = []
    carrier_positions: list[dict[str, object]] = []

    def finalize_measure() -> None:
        nonlocal measure_note_events
        if any(value != 0 for value in remaining.values()):
            raise Stage2QExactRuntimeAlignmentError("Joined measure ends while rhythmic duration remains")
        all_frames.extend(_frames_for_measure(measure_number, measure_note_events))
        measure_note_events = []

    for line in lines[header_index + 1 :]:
        if not line or line.startswith("!!"):
            continue
        if line.startswith("!"):
            continue
        cells = line.split("\t")
        if len(cells) != len(columns):
            raise Stage2QExactRuntimeAlignmentError("Joined static-spine row width changed")

        if line.startswith("*"):
            if any(cell in SPINE_PATH_TOKENS for cell in cells):
                raise Stage2QExactRuntimeAlignmentError("Joined spine path change is unsupported")
            if any(cell == "*-" for cell in cells):
                if not all(cell == "*-" for cell in cells):
                    raise Stage2QExactRuntimeAlignmentError("Joined partial spine termination is unsupported")
                if measure_started:
                    finalize_measure()
                measure_started = False
                continue
            for column_index in kern_indices:
                match = STAFF_RE.match(cells[column_index])
                if match:
                    staff = int(match.group(1))
                    if first_kern_data_seen and staffs[column_index] != staff:
                        raise Stage2QExactRuntimeAlignmentError("Joined staff reassignment after data is unsupported")
                    staffs[column_index] = staff
            continue

        if line.startswith("="):
            if not all(cell.startswith("=") for cell in cells):
                raise Stage2QExactRuntimeAlignmentError("Joined mixed barline/data row is unsupported")
            if measure_started:
                finalize_measure()
                measure_number += 1
            local_time = Fraction(0)
            measure_started = False
            continue

        if not all(staffs[index] is not None for index in kern_indices):
            raise Stage2QExactRuntimeAlignmentError("Joined **kern requires explicit *staffN before data")
        first_kern_data_seen = True
        row_onset = local_time
        new_value_seen = False

        for column_index in kern_indices:
            cell = cells[column_index].strip()
            if cell == ".":
                if remaining[column_index] <= 0:
                    raise Stage2QExactRuntimeAlignmentError("Joined **kern null token lacks sustain")
                continue
            if remaining[column_index] != 0:
                raise Stage2QExactRuntimeAlignmentError("Joined **kern token starts before prior duration ends")
            try:
                parsed = _parse_cell(cell)
            except Stage2PExactKernMaterializerError as exc:
                raise Stage2QExactRuntimeAlignmentError(str(exc)) from exc
            duration = parsed["duration"]
            if not isinstance(duration, Fraction):
                raise Stage2QExactRuntimeAlignmentError("Joined internal **kern duration is not exact")
            remaining[column_index] = duration
            new_value_seen = True
            for atom in parsed["atoms"]:
                if atom["rest"]:
                    continue
                measure_note_events.append(
                    {
                        "staff": staffs[column_index],
                        "voice": kern_ordinal[column_index],
                        "midi_pitch": atom["midi_pitch"],
                        "onset": row_onset,
                        "duration": duration,
                        "tie": atom["tie"],
                    }
                )

        harmonic = cells[harm_index].strip()
        if harmonic == ".":
            if remaining[harm_index] <= 0:
                raise Stage2QExactRuntimeAlignmentError("Joined **harm null token lacks sustain")
        elif _is_data_token(harmonic):
            if remaining[harm_index] != 0:
                raise Stage2QExactRuntimeAlignmentError("Joined **harm token starts before prior duration ends")
            duration = _harmonic_duration(harmonic)
            remaining[harm_index] = duration
            carrier_positions.append(
                {
                    "carrier_harmonic_event_index": len(carrier_positions),
                    "measure_number": measure_number,
                    "onset": _fraction_payload(row_onset),
                }
            )
            new_value_seen = True
        else:
            raise Stage2QExactRuntimeAlignmentError("unsupported Joined **harm data-row token")

        if not new_value_seen and not any(value > 0 for value in remaining.values()):
            raise Stage2QExactRuntimeAlignmentError("Joined data row has no active rhythmic value")
        positive = [value for value in remaining.values() if value > 0]
        if not positive:
            raise Stage2QExactRuntimeAlignmentError("Joined data row produced no positive duration")
        delta = min(positive)
        local_time += delta
        remaining = {
            index: (value - delta if value > 0 else value)
            for index, value in remaining.items()
        }
        if any(value < 0 for value in remaining.values()):
            raise Stage2QExactRuntimeAlignmentError("Joined rhythmic clock became negative")
        measure_started = True

    if measure_started:
        finalize_measure()
    if not carrier_positions:
        raise Stage2QExactRuntimeAlignmentError("Joined source has no harmonic carrier events")
    if not all_frames:
        raise Stage2QExactRuntimeAlignmentError("Joined source has no pitched runtime frames")
    return {"carrier_positions": carrier_positions, "frames": all_frames}


def audit_exact_source_path(
    events: list[dict[str, Any]], *, score_bytes: bytes, joined_bytes: bytes
) -> dict[str, object]:
    """Audit one Stage2G phrase/source path without exposing target values."""
    if not events:
        raise Stage2QExactRuntimeAlignmentError("empty Stage2G source path")
    try:
        score = materialize_exact_kern_runtime_frames(score_bytes)
    except Stage2PExactKernMaterializerError as exc:
        return {
            "event_count": len(events),
            "exact_aligned_event_count": 0,
            "score_materializer_supported": False,
            "joined_exact_timing_supported": False,
            "score_joined_frames_equivalent": False,
            "fully_exact_aligned": False,
            "path_failure_reason": "SCORE_STAGE2P_UNSUPPORTED",
            "event_failure_reasons": {"SCORE_STAGE2P_UNSUPPORTED": len(events)},
        }
    try:
        joined = _materialize_joined_carrier_and_frames(joined_bytes)
    except Stage2QExactRuntimeAlignmentError:
        return {
            "event_count": len(events),
            "exact_aligned_event_count": 0,
            "score_materializer_supported": True,
            "joined_exact_timing_supported": False,
            "score_joined_frames_equivalent": False,
            "fully_exact_aligned": False,
            "path_failure_reason": "JOINED_EXACT_TIMING_UNSUPPORTED",
            "event_failure_reasons": {"JOINED_EXACT_TIMING_UNSUPPORTED": len(events)},
        }

    score_frames = [_canonical_frame(row["frame"]) for row in score["frames"]]
    joined_frames = [_canonical_frame(frame) for frame in joined["frames"]]
    if score_frames != joined_frames:
        return {
            "event_count": len(events),
            "exact_aligned_event_count": 0,
            "score_materializer_supported": True,
            "joined_exact_timing_supported": True,
            "score_joined_frames_equivalent": False,
            "fully_exact_aligned": False,
            "path_failure_reason": "SCORE_JOINED_FRAME_MISMATCH",
            "event_failure_reasons": {"SCORE_JOINED_FRAME_MISMATCH": len(events)},
        }

    frame_by_start: dict[tuple[int, Fraction], str] = {}
    for row in score["frames"]:
        frame = row["frame"]
        key = (int(frame["measure_number"]), _payload_fraction(frame["start"]))
        if key in frame_by_start:
            raise Stage2QExactRuntimeAlignmentError("duplicate score runtime frame start")
        frame_by_start[key] = str(row["runtime_frame_id"])

    carriers = joined["carrier_positions"]
    failure_reasons: Counter[str] = Counter()
    aligned_ids: list[str] = []
    for event in sorted(events, key=lambda item: int(item["function_event_index"])):
        index = event.get("carrier_harmonic_event_index")
        if isinstance(index, bool) or not isinstance(index, int) or index < 0 or index >= len(carriers):
            failure_reasons["CARRIER_INDEX_OUT_OF_RANGE"] += 1
            continue
        carrier = carriers[index]
        key = (int(carrier["measure_number"]), _payload_fraction(carrier["onset"]))
        frame_id = frame_by_start.get(key)
        if frame_id is None:
            failure_reasons["CARRIER_NOT_RUNTIME_FRAME_START"] += 1
            continue
        aligned_ids.append(frame_id)

    duplicate_count = len(aligned_ids) - len(set(aligned_ids))
    if duplicate_count:
        failure_reasons["MULTIPLE_FUNCTION_EVENTS_SAME_RUNTIME_FRAME"] += duplicate_count
        # Duplicate joins are not usable as exact one-event-per-runtime-frame coverage.
        duplicate_ids = {frame_id for frame_id in aligned_ids if aligned_ids.count(frame_id) > 1}
        aligned_count = sum(frame_id not in duplicate_ids for frame_id in aligned_ids)
    else:
        aligned_count = len(aligned_ids)

    fully_exact = aligned_count == len(events) and not failure_reasons
    return {
        "event_count": len(events),
        "exact_aligned_event_count": aligned_count,
        "score_materializer_supported": True,
        "joined_exact_timing_supported": True,
        "score_joined_frames_equivalent": True,
        "fully_exact_aligned": fully_exact,
        "path_failure_reason": None if fully_exact else "EVENT_LEVEL_EXACT_JOIN_INCOMPLETE",
        "event_failure_reasons": dict(sorted(failure_reasons.items())),
    }


def run_stage2q_coverage_audit(stage2g_data: object, *, archive_path: str | Path) -> dict[str, object]:
    validate_stage2q_contract(build_stage2q_contract())
    events = _validate_stage2g_private_payload(stage2g_data)
    paths: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        if not isinstance(event, dict):
            raise Stage2QExactRuntimeAlignmentError("Stage2G event row malformed")
        phrase = event.get("phrase_key")
        source = event.get("source")
        fold = event.get("development_fold")
        if not isinstance(phrase, str) or not phrase or source not in {"A", "B"}:
            raise Stage2QExactRuntimeAlignmentError("Stage2G source-path identity malformed")
        if isinstance(fold, bool) or not isinstance(fold, int) or fold not in range(FOLD_COUNT):
            raise Stage2QExactRuntimeAlignmentError("Stage2G fold malformed")
        paths[(phrase, str(source))].append(event)
    if len(paths) != EXPECTED_STAGE2G_MATERIALIZABLE_SOURCE_PATH_COUNT:
        raise Stage2QExactRuntimeAlignmentError("Stage2G source-path count changed")

    archive_file = _bounded_regular_file(archive_path, max_bytes=MAX_ARCHIVE_BYTES, label="archive")
    digest = hashlib.sha256(archive_file.read_bytes()).hexdigest()
    if digest != PINNED_TAVERN_ARCHIVE_SHA256:
        raise Stage2QExactRuntimeAlignmentError("TAVERN archive SHA-256 mismatch")

    stats: Counter[str] = Counter()
    path_failure_reasons: Counter[str] = Counter()
    event_failure_reasons: Counter[str] = Counter()
    fold_aligned_events: Counter[int] = Counter()
    source_aligned_events: Counter[str] = Counter()
    score_cache: dict[str, bytes] = {}

    try:
        with zipfile.ZipFile(archive_file) as archive:
            infos = _validated_zip_members(archive)
            corrupt = archive.testzip()
            if corrupt is not None:
                raise Stage2QExactRuntimeAlignmentError(f"corrupt archive member: {corrupt}")
            root = _archive_root(infos)
            for (phrase, source), path_events in sorted(paths.items()):
                if phrase not in score_cache:
                    score_info = _score_member(infos, root=root, phrase_key=phrase)
                    if score_info.file_size > MAX_SCORE_BYTES:
                        raise Stage2QExactRuntimeAlignmentError("score source exceeds size bound")
                    score_cache[phrase] = archive.read(score_info)
                joined_info = _joined_member(infos, root=root, phrase_key=phrase, source=source)
                if joined_info.file_size > MAX_SOURCE_BYTES:
                    raise Stage2QExactRuntimeAlignmentError("Joined source exceeds size bound")
                result = audit_exact_source_path(
                    path_events,
                    score_bytes=score_cache[phrase],
                    joined_bytes=archive.read(joined_info),
                )
                stats["source_path_count"] += 1
                stats["event_count"] += int(result["event_count"])
                stats["exact_aligned_event_count"] += int(result["exact_aligned_event_count"])
                stats["score_materializer_supported_source_path_count"] += int(result["score_materializer_supported"] is True)
                stats["joined_exact_timing_supported_source_path_count"] += int(result["joined_exact_timing_supported"] is True)
                stats["score_joined_frame_equivalent_source_path_count"] += int(result["score_joined_frames_equivalent"] is True)
                stats["fully_exact_aligned_source_path_count"] += int(result["fully_exact_aligned"] is True)
                if result["path_failure_reason"] is not None:
                    path_failure_reasons[str(result["path_failure_reason"])] += 1
                for reason, count in dict(result["event_failure_reasons"]).items():
                    event_failure_reasons[str(reason)] += int(count)
                aligned = int(result["exact_aligned_event_count"])
                fold = int(path_events[0]["development_fold"])
                if any(int(item["development_fold"]) != fold for item in path_events):
                    raise Stage2QExactRuntimeAlignmentError("one Stage2G source path spans development folds")
                fold_aligned_events[fold] += aligned
                source_aligned_events[source] += aligned
    except zipfile.BadZipFile as exc:
        raise Stage2QExactRuntimeAlignmentError("invalid TAVERN ZIP archive") from exc

    if stats["source_path_count"] != EXPECTED_STAGE2G_MATERIALIZABLE_SOURCE_PATH_COUNT:
        raise Stage2QExactRuntimeAlignmentError("audited source-path count changed")
    if stats["event_count"] != EXPECTED_STAGE2G_EVENT_COUNT:
        raise Stage2QExactRuntimeAlignmentError("audited Stage2G event count changed")

    exact_events = stats["exact_aligned_event_count"]
    exact_paths = stats["fully_exact_aligned_source_path_count"]
    complete = (
        exact_events == EXPECTED_STAGE2G_EVENT_COUNT
        and exact_paths == EXPECTED_STAGE2G_MATERIALIZABLE_SOURCE_PATH_COUNT
    )
    summary = {
        "schema_version": SUMMARY_SCHEMA,
        "source_corpus": SOURCE_CORPUS,
        "eligible_original_partition": "TRAIN",
        "source_engine_stage2n_main_sha": EXPECTED_ENGINE_STAGE2N_SHA,
        "source_stage2g_private_event_manifest_sha256": EXPECTED_STAGE2G_PRIVATE_EVENT_MANIFEST_SHA256,
        "source_tavern_archive_sha256": PINNED_TAVERN_ARCHIVE_SHA256,
        "source_stage2p_materializer_version": MATERIALIZER_VERSION,
        "source_path_count": stats["source_path_count"],
        "materialized_event_count": stats["event_count"],
        "score_materializer_supported_source_path_count": stats["score_materializer_supported_source_path_count"],
        "joined_exact_timing_supported_source_path_count": stats["joined_exact_timing_supported_source_path_count"],
        "score_joined_frame_equivalent_source_path_count": stats["score_joined_frame_equivalent_source_path_count"],
        "fully_exact_aligned_source_path_count": exact_paths,
        "exact_aligned_event_count": exact_events,
        "unaligned_event_count": EXPECTED_STAGE2G_EVENT_COUNT - exact_events,
        "exact_event_alignment_coverage": round(exact_events / EXPECTED_STAGE2G_EVENT_COUNT, 12),
        "exact_source_path_alignment_coverage": round(exact_paths / EXPECTED_STAGE2G_MATERIALIZABLE_SOURCE_PATH_COUNT, 12),
        "fold_exact_aligned_event_distribution": {str(i): fold_aligned_events[i] for i in range(FOLD_COUNT)},
        "source_exact_aligned_event_distribution": {"A": source_aligned_events["A"], "B": source_aligned_events["B"]},
        "path_failure_reason_counts": dict(sorted(path_failure_reasons.items())),
        "event_failure_reason_counts": dict(sorted(event_failure_reasons.items())),
        "exact_stage2g_event_to_runtime_frame_alignment_complete": complete,
        "joined_harmonic_label_text_used": False,
        "joined_harmonic_reciprocal_used_as_exact_timing_evidence": True,
        "teacher_function_token_used_for_alignment": False,
        "nearest_frame_matching_used": False,
        "order_only_matching_used": False,
        "inferred_onset_used": False,
        "inferred_duration_used": False,
        "next_or_future_context_used": False,
        "partial_alignment_auto_admission_used": False,
        "runtime_frame_id_role": "JOIN_KEY_NOT_MODEL_FEATURE",
        "model_feature_materialization_authorized": False,
        "model_training_started": False,
        "model_selection_started": False,
        "full_train_final_fit_started": False,
        "non_train_access": False,
        "production_authority": False,
        "deterministic_resolver_remains_authoritative": True,
        "decision": (
            "EXACT_ALIGNMENT_COMPLETE_REVIEW_NEXT"
            if complete
            else "HOLD_PARTIAL_EXACT_ALIGNMENT_COVERAGE"
        ),
    }
    rendered = json.dumps(summary, sort_keys=True, ensure_ascii=False)
    for forbidden in ("function_token", "phrase_key", "carrier_event_id", "source_annotation_sha256"):
        if f'"{forbidden}"' in rendered:
            raise Stage2QExactRuntimeAlignmentError("shareable Stage 2-Q summary leaks private event data")
    return summary


def run_stage2q_coverage_audit_from_files(
    stage2g_private_path: str | Path, *, archive_path: str | Path
) -> dict[str, object]:
    require_locked_runtime()
    stage2g_data = load_bounded_json(stage2g_private_path, max_bytes=MAX_PRIVATE_BYTES)
    return run_stage2q_coverage_audit(stage2g_data, archive_path=archive_path)


def canonical_stage2q_json(data: dict[str, object]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
