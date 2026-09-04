"""Stage 2-Q corpus-reality correction for exact runtime alignment coverage.

The first Stage 2-Q contract was intentionally too narrow for the real TAVERN
Joined layout: every audited Joined file carries an additional **function spine
and omits explicit *staffN declarations that are present in the phrase score.
This correction preserves fail-closed semantics while allowing those two proven
structural facts without consuming Function label values as alignment evidence.
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

CONTRACT_SCHEMA = "st-stage2q-exact-runtime-alignment-coverage-contract-v2"
SUMMARY_SCHEMA = "st-stage2q-exact-runtime-alignment-coverage-summary-v2"
SOURCE_CORPUS = "TAVERN_REVIEWED_694"
EXPECTED_TRAINING_BASE_SHA = "17d86bd4b165a31fe2f9a724eaa27b65d2542714"
JOINED_TIMING_POLICY = "STATIC_**KERN_PLUS_SINGLE_**HARM_WITH_OPAQUE_**FUNCTION_PRESENCE_GUARD"
STAFF_MAPPING_POLICY = "PHRASE_SCORE_EXPLICIT_*staffN_BY_KERN_ORDINAL"
FRAME_JOIN_POLICY = "EXACT_MEASURE_AND_FRAME_START_ONLY"


class Stage2QCorpusRealityError(ValueError):
    pass


def build_stage2q_v2_contract() -> dict[str, object]:
    return {
        "schema_version": CONTRACT_SCHEMA,
        "stage": "STAGE_2_Q",
        "correction": "CORPUS_REALITY_V2",
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
        "staff_mapping_policy": STAFF_MAPPING_POLICY,
        "frame_join_policy": FRAME_JOIN_POLICY,
        "joined_function_spine_value_used": False,
        "joined_function_spine_presence_guard_only": True,
        "function_data_without_same_row_harmonic_data_authorized": False,
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


def validate_stage2q_v2_contract(data: object) -> dict[str, object]:
    expected = build_stage2q_v2_contract()
    if not isinstance(data, dict) or data != expected:
        raise Stage2QCorpusRealityError("Stage 2-Q v2 contract differs from frozen correction contract")
    return data


def _fraction_payload(value: Fraction) -> dict[str, int]:
    return {"numerator": value.numerator, "denominator": value.denominator}


def _payload_fraction(value: object) -> Fraction:
    if not isinstance(value, dict) or set(value) != {"numerator", "denominator"}:
        raise Stage2QCorpusRealityError("malformed rational payload")
    numerator = value["numerator"]
    denominator = value["denominator"]
    if isinstance(numerator, bool) or not isinstance(numerator, int):
        raise Stage2QCorpusRealityError("rational numerator must be int")
    if isinstance(denominator, bool) or not isinstance(denominator, int) or denominator <= 0:
        raise Stage2QCorpusRealityError("rational denominator must be positive int")
    return Fraction(numerator, denominator)


def _canonical_frame(frame: object) -> dict[str, Any]:
    return canonical_runtime_frame_identity_payload(frame, source_sha256="0" * 64)["frame"]


def _is_data_token(token: str) -> bool:
    return bool(token) and not token.startswith(("*", "=", "!", "."))


def _harmonic_duration(token: str) -> Fraction:
    match = DURATION_RE.match(token)
    if match is None or not match.group("body"):
        raise Stage2QCorpusRealityError("Joined harmonic event lacks explicit reciprocal")
    return _reciprocal_to_quarter_length(match.group("recip"), len(match.group("dots")))


def _score_staff_map(raw_score_bytes: bytes) -> tuple[int, ...]:
    if not isinstance(raw_score_bytes, bytes):
        raise TypeError("raw_score_bytes must be bytes")
    try:
        text = raw_score_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise Stage2QCorpusRealityError("score source is not strict UTF-8") from exc
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    headers = [index for index, line in enumerate(lines) if line.startswith("**")]
    if len(headers) != 1:
        raise Stage2QCorpusRealityError("score source must contain one exclusive header")
    header = headers[0]
    columns = lines[header].split("\t")
    if not columns or any(value != "**kern" for value in columns):
        raise Stage2QCorpusRealityError("score staff mapping requires only **kern spines")
    staffs: list[int | None] = [None] * len(columns)
    for line in lines[header + 1 :]:
        if not line or line.startswith("!"):
            continue
        cells = line.split("\t")
        if len(cells) != len(columns):
            raise Stage2QCorpusRealityError("score row width changed before first data")
        if line.startswith("*"):
            if any(cell in SPINE_PATH_TOKENS for cell in cells):
                raise Stage2QCorpusRealityError("score spine path changed before first data")
            for index, cell in enumerate(cells):
                match = STAFF_RE.match(cell)
                if match:
                    staffs[index] = int(match.group(1))
            continue
        if line.startswith("="):
            continue
        break
    if any(value is None for value in staffs):
        raise Stage2QCorpusRealityError("score lacks complete explicit *staffN mapping")
    return tuple(int(value) for value in staffs)


def _materialize_joined_with_score_staffs(
    raw_joined_bytes: bytes,
    *,
    score_staffs: tuple[int, ...],
) -> dict[str, object]:
    if not isinstance(raw_joined_bytes, bytes):
        raise TypeError("raw_joined_bytes must be bytes")
    if not raw_joined_bytes or len(raw_joined_bytes) > MAX_SOURCE_BYTES:
        raise Stage2QCorpusRealityError("Joined source is empty or exceeds size bound")
    try:
        text = raw_joined_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise Stage2QCorpusRealityError("Joined source is not strict UTF-8") from exc
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if len(lines) > MAX_LINES:
        raise Stage2QCorpusRealityError("Joined line count exceeds bound")

    headers = [index for index, line in enumerate(lines) if line.startswith("**")]
    if len(headers) != 1:
        raise Stage2QCorpusRealityError("Joined source must contain one exclusive header")
    header = headers[0]
    columns = lines[header].split("\t")
    kern_indices = [index for index, value in enumerate(columns) if value == "**kern"]
    harm_indices = [index for index, value in enumerate(columns) if value == "**harm"]
    function_indices = [index for index, value in enumerate(columns) if value == "**function"]
    if not kern_indices or len(kern_indices) > MAX_KERN_SPINES:
        raise Stage2QCorpusRealityError("Joined source has unsupported **kern spine count")
    if len(kern_indices) != len(score_staffs):
        raise Stage2QCorpusRealityError("Joined **kern spine count differs from phrase score")
    if len(harm_indices) != 1:
        raise Stage2QCorpusRealityError("Joined source must contain exactly one **harm spine")
    if len(function_indices) > 1:
        raise Stage2QCorpusRealityError("Joined source contains multiple **function spines")
    if any(value not in {"**kern", "**harm", "**function"} for value in columns):
        raise Stage2QCorpusRealityError("Joined exact audit rejects unknown spine types")

    harm_index = harm_indices[0]
    function_index = function_indices[0] if function_indices else None
    kern_ordinal = {column_index: ordinal + 1 for ordinal, column_index in enumerate(kern_indices)}
    staff_by_column = {
        column_index: score_staffs[ordinal]
        for ordinal, column_index in enumerate(kern_indices)
    }
    remaining: dict[int, Fraction] = {column_index: Fraction(0) for column_index in kern_indices}
    remaining[harm_index] = Fraction(0)
    measure_number = 1
    local_time = Fraction(0)
    measure_started = False
    note_events: list[dict[str, object]] = []
    frames: list[dict[str, object]] = []
    carriers: list[dict[str, object]] = []

    def finalize_measure() -> None:
        nonlocal note_events
        if any(value != 0 for value in remaining.values()):
            raise Stage2QCorpusRealityError("Joined measure ends while rhythmic duration remains")
        frames.extend(_frames_for_measure(measure_number, note_events))
        note_events = []

    for line in lines[header + 1 :]:
        if not line or line.startswith("!!"):
            continue
        if line.startswith("!"):
            continue
        cells = line.split("\t")
        if len(cells) != len(columns):
            raise Stage2QCorpusRealityError("Joined static-spine row width changed")
        if line.startswith("*"):
            if any(cell in SPINE_PATH_TOKENS for cell in cells):
                raise Stage2QCorpusRealityError("Joined spine path change is unsupported")
            if any(cell == "*-" for cell in cells):
                if not all(cell == "*-" for cell in cells):
                    raise Stage2QCorpusRealityError("Joined partial spine termination is unsupported")
                if measure_started:
                    finalize_measure()
                measure_started = False
                continue
            for ordinal, column_index in enumerate(kern_indices):
                match = STAFF_RE.match(cells[column_index])
                if match and int(match.group(1)) != score_staffs[ordinal]:
                    raise Stage2QCorpusRealityError("Joined explicit staff conflicts with phrase score")
            continue
        if line.startswith("="):
            if not all(cell.startswith("=") for cell in cells):
                raise Stage2QCorpusRealityError("Joined mixed barline/data row is unsupported")
            if measure_started:
                finalize_measure()
                measure_number += 1
            local_time = Fraction(0)
            measure_started = False
            continue

        row_onset = local_time
        for column_index in kern_indices:
            cell = cells[column_index].strip()
            if cell == ".":
                if remaining[column_index] <= 0:
                    raise Stage2QCorpusRealityError("Joined **kern null token lacks sustain")
                continue
            if remaining[column_index] != 0:
                raise Stage2QCorpusRealityError("Joined **kern token starts before prior duration ends")
            try:
                parsed = _parse_cell(cell)
            except Stage2PExactKernMaterializerError as exc:
                raise Stage2QCorpusRealityError(str(exc)) from exc
            duration = parsed["duration"]
            if not isinstance(duration, Fraction):
                raise Stage2QCorpusRealityError("Joined internal **kern duration is not exact")
            remaining[column_index] = duration
            for atom in parsed["atoms"]:
                if atom["rest"]:
                    continue
                note_events.append(
                    {
                        "staff": staff_by_column[column_index],
                        "voice": kern_ordinal[column_index],
                        "midi_pitch": atom["midi_pitch"],
                        "onset": row_onset,
                        "duration": duration,
                        "tie": atom["tie"],
                    }
                )

        harmonic = cells[harm_index].strip()
        harmonic_is_data = _is_data_token(harmonic)
        if harmonic == ".":
            if remaining[harm_index] <= 0:
                raise Stage2QCorpusRealityError("Joined **harm null token lacks sustain")
        elif harmonic_is_data:
            if remaining[harm_index] != 0:
                raise Stage2QCorpusRealityError("Joined **harm token starts before prior duration ends")
            duration = _harmonic_duration(harmonic)
            remaining[harm_index] = duration
            carriers.append(
                {
                    "carrier_harmonic_event_index": len(carriers),
                    "measure_number": measure_number,
                    "onset": _fraction_payload(row_onset),
                }
            )
        else:
            raise Stage2QCorpusRealityError("unsupported Joined **harm data-row token")

        if function_index is not None:
            function_token = cells[function_index].strip()
            if _is_data_token(function_token) and not harmonic_is_data:
                raise Stage2QCorpusRealityError("Function data appears without same-row harmonic carrier")

        positive = [value for value in remaining.values() if value > 0]
        if not positive:
            raise Stage2QCorpusRealityError("Joined data row produced no positive tracked duration")
        delta = min(positive)
        local_time += delta
        remaining = {
            index: (value - delta if value > 0 else value)
            for index, value in remaining.items()
        }
        if any(value < 0 for value in remaining.values()):
            raise Stage2QCorpusRealityError("Joined rhythmic clock became negative")
        measure_started = True

    if measure_started:
        finalize_measure()
    if not carriers or not frames:
        raise Stage2QCorpusRealityError("Joined source lacks carriers or pitched frames")
    return {"carrier_positions": carriers, "frames": frames}


def audit_exact_source_path_v2(
    events: list[dict[str, Any]],
    *,
    score_bytes: bytes,
    joined_bytes: bytes,
) -> dict[str, object]:
    if not events:
        raise Stage2QCorpusRealityError("empty Stage2G source path")
    try:
        score = materialize_exact_kern_runtime_frames(score_bytes)
        score_staffs = _score_staff_map(score_bytes)
    except (Stage2PExactKernMaterializerError, Stage2QCorpusRealityError):
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
        joined = _materialize_joined_with_score_staffs(joined_bytes, score_staffs=score_staffs)
    except Stage2QCorpusRealityError:
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
            raise Stage2QCorpusRealityError("duplicate score runtime frame start")
        frame_by_start[key] = str(row["runtime_frame_id"])

    carriers = joined["carrier_positions"]
    failures: Counter[str] = Counter()
    aligned_ids: list[str] = []
    for event in sorted(events, key=lambda item: int(item["function_event_index"])):
        index = event.get("carrier_harmonic_event_index")
        if isinstance(index, bool) or not isinstance(index, int) or index < 0 or index >= len(carriers):
            failures["CARRIER_INDEX_OUT_OF_RANGE"] += 1
            continue
        carrier = carriers[index]
        key = (int(carrier["measure_number"]), _payload_fraction(carrier["onset"]))
        frame_id = frame_by_start.get(key)
        if frame_id is None:
            failures["CARRIER_NOT_RUNTIME_FRAME_START"] += 1
            continue
        aligned_ids.append(frame_id)

    duplicate_ids = {frame_id for frame_id in aligned_ids if aligned_ids.count(frame_id) > 1}
    if duplicate_ids:
        failures["MULTIPLE_FUNCTION_EVENTS_SAME_RUNTIME_FRAME"] += sum(
            frame_id in duplicate_ids for frame_id in aligned_ids
        )
    aligned_count = sum(frame_id not in duplicate_ids for frame_id in aligned_ids)
    fully_exact = aligned_count == len(events) and not failures
    return {
        "event_count": len(events),
        "exact_aligned_event_count": aligned_count,
        "score_materializer_supported": True,
        "joined_exact_timing_supported": True,
        "score_joined_frames_equivalent": True,
        "fully_exact_aligned": fully_exact,
        "path_failure_reason": None if fully_exact else "EVENT_LEVEL_EXACT_JOIN_INCOMPLETE",
        "event_failure_reasons": dict(sorted(failures.items())),
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_stage2q_v2_coverage_audit(stage2g_data: object, *, archive_path: str | Path) -> dict[str, object]:
    validate_stage2q_v2_contract(build_stage2q_v2_contract())
    events = _validate_stage2g_private_payload(stage2g_data)
    paths: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        if not isinstance(event, dict):
            raise Stage2QCorpusRealityError("Stage2G event row malformed")
        phrase = event.get("phrase_key")
        source = event.get("source")
        fold = event.get("development_fold")
        if not isinstance(phrase, str) or not phrase or source not in {"A", "B"}:
            raise Stage2QCorpusRealityError("Stage2G source-path identity malformed")
        if isinstance(fold, bool) or not isinstance(fold, int) or fold not in range(FOLD_COUNT):
            raise Stage2QCorpusRealityError("Stage2G fold malformed")
        paths[(phrase, str(source))].append(event)
    if len(paths) != EXPECTED_STAGE2G_MATERIALIZABLE_SOURCE_PATH_COUNT:
        raise Stage2QCorpusRealityError("Stage2G source-path count changed")

    archive_file = _bounded_regular_file(archive_path, max_bytes=MAX_ARCHIVE_BYTES, label="archive")
    if _sha256_file(archive_file) != PINNED_TAVERN_ARCHIVE_SHA256:
        raise Stage2QCorpusRealityError("TAVERN archive SHA-256 mismatch")

    stats: Counter[str] = Counter()
    path_failures: Counter[str] = Counter()
    event_failures: Counter[str] = Counter()
    fold_aligned: Counter[int] = Counter()
    source_aligned: Counter[str] = Counter()
    score_cache: dict[str, bytes] = {}

    try:
        with zipfile.ZipFile(archive_file) as archive:
            infos = _validated_zip_members(archive)
            corrupt = archive.testzip()
            if corrupt is not None:
                raise Stage2QCorpusRealityError(f"corrupt archive member: {corrupt}")
            root = _archive_root(infos)
            for (phrase, source), path_events in sorted(paths.items()):
                if phrase not in score_cache:
                    score_info = _score_member(infos, root=root, phrase_key=phrase)
                    if score_info.file_size > MAX_SCORE_BYTES:
                        raise Stage2QCorpusRealityError("score source exceeds size bound")
                    score_cache[phrase] = archive.read(score_info)
                joined_info = _joined_member(infos, root=root, phrase_key=phrase, source=source)
                if joined_info.file_size > MAX_SOURCE_BYTES:
                    raise Stage2QCorpusRealityError("Joined source exceeds size bound")
                result = audit_exact_source_path_v2(
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
                    path_failures[str(result["path_failure_reason"])] += 1
                for reason, count in dict(result["event_failure_reasons"]).items():
                    event_failures[str(reason)] += int(count)
                aligned = int(result["exact_aligned_event_count"])
                fold = int(path_events[0]["development_fold"])
                if any(int(item["development_fold"]) != fold for item in path_events):
                    raise Stage2QCorpusRealityError("one Stage2G source path spans development folds")
                fold_aligned[fold] += aligned
                source_aligned[source] += aligned
    except zipfile.BadZipFile as exc:
        raise Stage2QCorpusRealityError("invalid TAVERN ZIP archive") from exc

    if stats["source_path_count"] != EXPECTED_STAGE2G_MATERIALIZABLE_SOURCE_PATH_COUNT:
        raise Stage2QCorpusRealityError("audited source-path count changed")
    if stats["event_count"] != EXPECTED_STAGE2G_EVENT_COUNT:
        raise Stage2QCorpusRealityError("audited event count changed")

    exact_events = stats["exact_aligned_event_count"]
    exact_paths = stats["fully_exact_aligned_source_path_count"]
    complete = exact_events == EXPECTED_STAGE2G_EVENT_COUNT and exact_paths == EXPECTED_STAGE2G_MATERIALIZABLE_SOURCE_PATH_COUNT
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
        "fold_exact_aligned_event_distribution": {str(i): fold_aligned[i] for i in range(FOLD_COUNT)},
        "source_exact_aligned_event_distribution": {"A": source_aligned["A"], "B": source_aligned["B"]},
        "path_failure_reason_counts": dict(sorted(path_failures.items())),
        "event_failure_reason_counts": dict(sorted(event_failures.items())),
        "exact_stage2g_event_to_runtime_frame_alignment_complete": complete,
        "joined_function_spine_value_used": False,
        "joined_function_spine_presence_guard_only": True,
        "joined_harmonic_label_text_used": False,
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
        "decision": "EXACT_ALIGNMENT_COMPLETE_REVIEW_NEXT" if complete else "HOLD_PARTIAL_EXACT_ALIGNMENT_COVERAGE",
    }
    rendered = json.dumps(summary, sort_keys=True, ensure_ascii=False)
    for forbidden in ("function_token", "phrase_key", "carrier_event_id", "source_annotation_sha256"):
        if f'"{forbidden}"' in rendered:
            raise Stage2QCorpusRealityError("shareable Stage 2-Q v2 summary leaks private event data")
    return summary


def run_stage2q_v2_coverage_audit_from_files(
    stage2g_private_path: str | Path,
    *,
    archive_path: str | Path,
) -> dict[str, object]:
    require_locked_runtime()
    stage2g_data = load_bounded_json(stage2g_private_path, max_bytes=MAX_PRIVATE_BYTES)
    return run_stage2q_v2_coverage_audit(stage2g_data, archive_path=archive_path)


def canonical_stage2q_v2_json(data: dict[str, object]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
