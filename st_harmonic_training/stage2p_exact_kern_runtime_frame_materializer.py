"""Stage 2-P exact bounded **kern -> engine runtime-frame materializer.

The materializer implements a deliberately narrow, fail-closed subset of Humdrum
**kern sufficient to establish exact source timing when the source stays inside
the supported contract. Unsupported spine-path changes or ambiguous rhythmic
constructs are rejected rather than approximated.
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import re
from typing import Any

from .stage2o_runtime_frame_identity_preflight import runtime_frame_id_from_primitives

CONTRACT_SCHEMA = "st-stage2p-exact-kern-runtime-frame-materializer-contract-v1"
SUMMARY_SCHEMA = "st-stage2p-exact-kern-runtime-frame-materializer-summary-v1"
MATERIALIZER_VERSION = "st-stage2p-static-kern-runtime-frame-v1"
MAX_SOURCE_BYTES = 2_000_000
MAX_LINES = 20_000
MAX_KERN_SPINES = 16
MAX_ATOMS_PER_CELL = 32
MAX_TOKEN_CHARS = 512
SPINE_PATH_TOKENS = frozenset({"*^", "*v", "*x", "*+"})
DURATION_RE = re.compile(
    r"^(?P<prefix>[^0-9]*?)(?P<recip>(?:0+|[1-9][0-9]*(?:%[1-9][0-9]*)?))(?P<dots>\.*)(?P<body>.*)$"
)
PITCH_RE = re.compile(r"(?P<letters>[A-Ga-g]+)(?P<accidental>#{1,4}|-{1,4}|n)?")
STAFF_RE = re.compile(r"^\*staff([1-9][0-9]*)$")


class Stage2PExactKernMaterializerError(ValueError):
    pass


def build_stage2p_contract() -> dict[str, object]:
    return {
        "schema_version": CONTRACT_SCHEMA,
        "stage": "STAGE_2_P",
        "source_representation": "HUMDRUM_**KERN",
        "eligible_original_partition": "TRAIN",
        "materializer_version": MATERIALIZER_VERSION,
        "measure_number_policy": "PHRASE_LOCAL_ONE_BASED_SEQUENTIAL",
        "voice_policy": "ONE_BASED_INITIAL_KERN_SPINE_ORDINAL",
        "staff_policy": "EXPLICIT_*staffN_REQUIRED_BEFORE_FIRST_DATA",
        "rhythm_policy": "EXACT_RECIPROCAL_WITH_NULL_SUSTAIN_SEMANTICS",
        "multiple_stop_policy": "ALL_ATOMS_MUST_HAVE_EXACT_EQUAL_DURATION",
        "spine_path_split_join_exchange_add_supported": False,
        "partial_spine_termination_supported": False,
        "grace_note_materialization_supported": False,
        "heuristic_timing_recovery_authorized": False,
        "inferred_duration_authorized": False,
        "inferred_onset_authorized": False,
        "harmonic_label_assisted_alignment_authorized": False,
        "teacher_target_assisted_alignment_authorized": False,
        "runtime_frame_id_role": "JOIN_KEY_NOT_MODEL_FEATURE",
        "model_feature_materialization_authorized": False,
        "model_training_started": False,
        "non_train_access_authorized": False,
        "production_authority": False,
        "deterministic_resolver_remains_authoritative": True,
    }


def _reciprocal_to_quarter_length(recip: str, dots: int) -> Fraction:
    if not isinstance(recip, str) or not recip:
        raise Stage2PExactKernMaterializerError("empty reciprocal duration")
    if isinstance(dots, bool) or not isinstance(dots, int) or dots < 0 or dots > 8:
        raise Stage2PExactKernMaterializerError("unsupported augmentation dot count")

    if set(recip) == {"0"}:
        # **kern: 0=breve=2 whole notes, 00=long=4 wholes, 000=maxima=8 wholes.
        whole_length = Fraction(2 ** len(recip), 1)
    elif "%" in recip:
        numerator_text, denominator_text = recip.split("%", 1)
        numerator = int(numerator_text)
        denominator = int(denominator_text)
        if numerator <= 0 or denominator <= 0:
            raise Stage2PExactKernMaterializerError("invalid extended reciprocal")
        whole_length = Fraction(denominator, numerator)
    else:
        denominator = int(recip)
        if denominator <= 0:
            raise Stage2PExactKernMaterializerError("invalid reciprocal")
        whole_length = Fraction(1, denominator)

    dot_factor = sum((Fraction(1, 2**index) for index in range(dots + 1)), Fraction(0))
    quarter_length = whole_length * 4 * dot_factor
    if quarter_length <= 0:
        raise Stage2PExactKernMaterializerError("non-positive duration")
    return quarter_length


def _fraction_payload(value: Fraction) -> dict[str, int]:
    return {"numerator": value.numerator, "denominator": value.denominator}


def _tie_state(atom: str) -> str:
    markers = {marker for marker in ("[", "_", "]") if marker in atom}
    if len(markers) > 1:
        raise Stage2PExactKernMaterializerError("ambiguous multiple tie markers in one note atom")
    if "[" in markers:
        return "start"
    if "_" in markers:
        return "continue"
    if "]" in markers:
        return "stop"
    return "none"


def _pitch_to_midi(letters: str, accidental: str | None) -> int:
    if not letters:
        raise Stage2PExactKernMaterializerError("missing pitch letters")
    first = letters[0]
    if any(char != first for char in letters):
        raise Stage2PExactKernMaterializerError("mixed pitch letters in **kern pitch atom")
    count = len(letters)
    if first.islower():
        octave = 3 + count
    else:
        octave = 4 - count
    pitch_class = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[first.upper()]
    if accidental is None or accidental == "n":
        alteration = 0
    elif set(accidental) == {"#"}:
        alteration = len(accidental)
    elif set(accidental) == {"-"}:
        alteration = -len(accidental)
    else:
        raise Stage2PExactKernMaterializerError("unsupported accidental")
    midi = 12 * (octave + 1) + pitch_class + alteration
    if midi < 0 or midi > 127:
        raise Stage2PExactKernMaterializerError("pitch outside MIDI 0..127")
    return midi


def _parse_atom(atom: str) -> dict[str, object]:
    if not atom or len(atom) > MAX_TOKEN_CHARS:
        raise Stage2PExactKernMaterializerError("empty or oversized **kern atom")
    match = DURATION_RE.match(atom)
    if match is None:
        raise Stage2PExactKernMaterializerError(f"explicit reciprocal duration required: {atom}")
    body = match.group("body")
    prefix = match.group("prefix")
    if any(marker in atom for marker in ("q", "p", "P", "Q")):
        raise Stage2PExactKernMaterializerError("grace/appoggiatura materialization is not supported")
    duration = _reciprocal_to_quarter_length(match.group("recip"), len(match.group("dots")))
    tie = _tie_state(atom)

    pitch_matches = list(PITCH_RE.finditer(body))
    is_rest = "r" in body.lower() and not pitch_matches
    if is_rest:
        if tie != "none":
            raise Stage2PExactKernMaterializerError("rest cannot carry a tie marker")
        return {"duration": duration, "rest": True, "midi_pitch": None, "tie": "none"}
    if len(pitch_matches) != 1:
        raise Stage2PExactKernMaterializerError(f"exactly one pitch required per atom: {atom}")
    pitch = pitch_matches[0]
    letters = pitch.group("letters")
    accidental = pitch.group("accidental")
    if "n" in body and accidental != "n":
        raise Stage2PExactKernMaterializerError("natural sign is not attached to the parsed pitch")
    if "#" in body and accidental is None:
        raise Stage2PExactKernMaterializerError("sharp sign is not attached to the parsed pitch")
    # A minus sign before/after the pitch can be an accidental only when captured by PITCH_RE.
    if "-" in body and accidental is None:
        raise Stage2PExactKernMaterializerError("flat sign is not attached to the parsed pitch")
    return {
        "duration": duration,
        "rest": False,
        "midi_pitch": _pitch_to_midi(letters, accidental),
        "tie": tie,
    }


def _parse_cell(cell: str) -> dict[str, object]:
    if not cell or len(cell) > MAX_TOKEN_CHARS:
        raise Stage2PExactKernMaterializerError("empty or oversized **kern cell")
    atoms = cell.split()
    if not atoms or len(atoms) > MAX_ATOMS_PER_CELL:
        raise Stage2PExactKernMaterializerError("unsupported multiple-stop size")
    parsed = [_parse_atom(atom) for atom in atoms]
    durations = {item["duration"] for item in parsed}
    if len(durations) != 1:
        raise Stage2PExactKernMaterializerError("multiple-stop atoms must have equal exact duration")
    rests = [item for item in parsed if item["rest"]]
    if rests and len(parsed) != 1:
        raise Stage2PExactKernMaterializerError("rest cannot share a multiple-stop cell with notes")
    return {"duration": parsed[0]["duration"], "atoms": parsed}


def _frames_for_measure(measure_number: int, note_events: list[dict[str, object]]) -> list[dict[str, object]]:
    if not note_events:
        return []
    boundaries: set[Fraction] = set()
    normalized: list[tuple[dict[str, object], Fraction, Fraction]] = []
    for event in note_events:
        onset_raw = event["onset"]
        duration_raw = event["duration"]
        if not isinstance(onset_raw, Fraction) or not isinstance(duration_raw, Fraction):
            raise Stage2PExactKernMaterializerError("internal event timing is not exact")
        end = onset_raw + duration_raw
        boundaries.add(onset_raw)
        boundaries.add(end)
        normalized.append((event, onset_raw, end))
    ordered = sorted(boundaries)
    frames: list[dict[str, object]] = []
    for start, end in zip(ordered, ordered[1:]):
        if end <= start:
            raise Stage2PExactKernMaterializerError("non-increasing frame boundary")
        active = [event for event, onset, event_end in normalized if onset <= start and event_end >= end]
        if not active:
            continue
        rendered_events = []
        for event in active:
            rendered_events.append(
                {
                    "measure_number": measure_number,
                    "staff": event["staff"],
                    "voice": event["voice"],
                    "midi_pitch": event["midi_pitch"],
                    "onset": _fraction_payload(event["onset"]),
                    "duration": _fraction_payload(event["duration"]),
                    "tie": event["tie"],
                }
            )
        frames.append(
            {
                "measure_number": measure_number,
                "start": _fraction_payload(start),
                "end": _fraction_payload(end),
                "events": rendered_events,
            }
        )
    return frames


def materialize_exact_kern_runtime_frames(raw_score_bytes: bytes) -> dict[str, object]:
    """Materialize exact engine-frame primitives for the supported static-spine subset."""
    if not isinstance(raw_score_bytes, bytes):
        raise TypeError("raw_score_bytes must be bytes")
    if not raw_score_bytes or len(raw_score_bytes) > MAX_SOURCE_BYTES:
        raise Stage2PExactKernMaterializerError("score source is empty or exceeds size bound")
    source_sha256 = hashlib.sha256(raw_score_bytes).hexdigest()
    try:
        text = raw_score_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise Stage2PExactKernMaterializerError("score source is not strict UTF-8") from exc
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if len(lines) > MAX_LINES:
        raise Stage2PExactKernMaterializerError("score line count exceeds bound")

    header_indices = [index for index, line in enumerate(lines) if line.startswith("**")]
    if len(header_indices) != 1:
        raise Stage2PExactKernMaterializerError("expected exactly one exclusive interpretation header")
    header_index = header_indices[0]
    columns = lines[header_index].split("\t")
    if not columns or len(columns) > MAX_KERN_SPINES or any(cell != "**kern" for cell in columns):
        raise Stage2PExactKernMaterializerError("Stage 2-P requires only bounded **kern spines")
    spine_count = len(columns)
    staffs: list[int | None] = [None] * spine_count
    remaining: list[Fraction] = [Fraction(0)] * spine_count
    first_data_seen = False
    local_time = Fraction(0)
    measure_number = 1
    measure_started = False
    measure_note_events: list[dict[str, object]] = []
    all_frames: list[dict[str, object]] = []
    data_row_count = 0

    def finalize_measure() -> None:
        nonlocal measure_note_events
        if any(value != 0 for value in remaining):
            raise Stage2PExactKernMaterializerError("barline/termination reached while a spine duration remains")
        all_frames.extend(_frames_for_measure(measure_number, measure_note_events))
        measure_note_events = []

    for line in lines[header_index + 1 :]:
        if not line or line.startswith("!!"):
            continue
        cells = line.split("\t")
        if line.startswith("!"):
            continue
        if len(cells) != spine_count:
            raise Stage2PExactKernMaterializerError("static-spine row width changed")

        if line.startswith("*"):
            if any(cell in SPINE_PATH_TOKENS for cell in cells):
                raise Stage2PExactKernMaterializerError("spine split/join/exchange/add is unsupported")
            if any(cell == "*-" for cell in cells):
                if not all(cell == "*-" for cell in cells):
                    raise Stage2PExactKernMaterializerError("partial spine termination is unsupported")
                if measure_started:
                    finalize_measure()
                measure_started = False
                continue
            for index, cell in enumerate(cells):
                staff_match = STAFF_RE.match(cell)
                if staff_match:
                    if first_data_seen and staffs[index] != int(staff_match.group(1)):
                        raise Stage2PExactKernMaterializerError("staff reassignment after data is unsupported")
                    staffs[index] = int(staff_match.group(1))
            continue

        if line.startswith("="):
            if not all(cell.startswith("=") for cell in cells):
                raise Stage2PExactKernMaterializerError("mixed barline/data row is unsupported")
            if measure_started:
                finalize_measure()
                measure_number += 1
            local_time = Fraction(0)
            measure_started = False
            continue

        if not all(staff is not None for staff in staffs):
            raise Stage2PExactKernMaterializerError("explicit *staffN required before first data")
        first_data_seen = True
        measure_started = True
        data_row_count += 1
        new_event_seen = False
        for index, cell in enumerate(cells):
            if cell == ".":
                if remaining[index] <= 0:
                    raise Stage2PExactKernMaterializerError("null token has no sustaining note/rest")
                continue
            if remaining[index] != 0:
                raise Stage2PExactKernMaterializerError("new token begins before prior spine duration ends")
            parsed = _parse_cell(cell)
            duration = parsed["duration"]
            if not isinstance(duration, Fraction):
                raise Stage2PExactKernMaterializerError("internal cell duration is not exact")
            remaining[index] = duration
            new_event_seen = True
            for atom in parsed["atoms"]:
                if atom["rest"]:
                    continue
                measure_note_events.append(
                    {
                        "staff": staffs[index],
                        "voice": index + 1,
                        "midi_pitch": atom["midi_pitch"],
                        "onset": local_time,
                        "duration": duration,
                        "tie": atom["tie"],
                    }
                )
        if not new_event_seen:
            raise Stage2PExactKernMaterializerError("all-null data row is unsupported")
        positive = [value for value in remaining if value > 0]
        if not positive:
            raise Stage2PExactKernMaterializerError("data row produced no positive duration")
        delta = min(positive)
        local_time += delta
        remaining = [value - delta if value > 0 else value for value in remaining]
        if any(value < 0 for value in remaining):
            raise Stage2PExactKernMaterializerError("negative remaining duration")

    if measure_started:
        finalize_measure()
    if data_row_count == 0:
        raise Stage2PExactKernMaterializerError("score contains no data rows")
    if not all_frames:
        raise Stage2PExactKernMaterializerError("score contains no pitched runtime frames")

    frame_rows = []
    seen_ids: set[str] = set()
    for frame_index, frame in enumerate(all_frames):
        frame_id = runtime_frame_id_from_primitives(frame, source_sha256=source_sha256)
        if frame_id in seen_ids:
            raise Stage2PExactKernMaterializerError("duplicate exact runtime-frame identity")
        seen_ids.add(frame_id)
        frame_rows.append({"frame_index": frame_index, "runtime_frame_id": frame_id, "frame": frame})

    return {
        "schema_version": SUMMARY_SCHEMA,
        "materializer_version": MATERIALIZER_VERSION,
        "source_sha256": source_sha256,
        "kern_spine_count": spine_count,
        "data_row_count": data_row_count,
        "runtime_frame_count": len(frame_rows),
        "measure_count": len({row["frame"]["measure_number"] for row in frame_rows}),
        "frames": frame_rows,
        "exact_source_timing_materialized": True,
        "heuristic_timing_recovery_used": False,
        "inferred_duration_used": False,
        "inferred_onset_used": False,
        "harmonic_label_assisted_alignment_used": False,
        "teacher_target_assisted_alignment_used": False,
        "runtime_frame_id_role": "JOIN_KEY_NOT_MODEL_FEATURE",
        "model_feature_materialization_authorized": False,
        "model_training_started": False,
        "production_authority": False,
        "deterministic_resolver_remains_authoritative": True,
    }
