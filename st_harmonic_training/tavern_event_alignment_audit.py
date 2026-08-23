from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile
from typing import Any

from .tavern_gold_materialization import PINNED_COUNT, PINNED_VALIDATED_SHA256
from .tavern_raw_label_realization import (
    MAX_ARCHIVE_BYTES,
    PINNED_TAVERN_ARCHIVE_SHA256,
    _bounded_regular_file,
    _validated_zip_members,
)
from .tavern_score_input_realization import _archive_root
from .tavern_structure import PINNED_TAVERN_REVISION

ALIGNMENT_SCHEMA = "st-tavern-event-alignment-audit-v1"
SUMMARY_SCHEMA = "st-tavern-event-alignment-audit-summary-v1"
EXPECTED_SELECTED_TARGET_COUNT = 747
PINNED_ALIGNMENT_MANIFEST_SHA256 = (
    "95fdae9b9d336eb9c50646b2c980954d54c87dac95902974b1836dad77ff7552"
)
SAFE_PHRASE_RE = re.compile(
    r"^(Beethoven|Mozart)/([A-Za-z0-9]+):(\d{2}):(\d{2})$"
)
JOINED_NAME_RE = re.compile(
    r"^[A-Za-z0-9]+_(\d{2})_(\d{2})(?:[a-z])?_([ab])\.krn$"
)
RECIPROCAL_PREFIX_RE = re.compile(r"^(\(*)(\d+(?:%\d+)?\.*)(.+)$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class TavernEventAlignmentError(ValueError):
    pass


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _selected_sources(item: dict[str, Any]) -> list[str]:
    decision = item.get("decision")
    if decision == "SELECT_A":
        return ["A"]
    if decision == "SELECT_B":
        return ["B"]
    if decision == "PRESERVE_VARIANTS":
        return ["A", "B"]
    raise TavernEventAlignmentError(f"unsupported validated decision: {decision}")


def _encoder_member(
    infos: list[zipfile.ZipInfo], *, root: str, phrase_key: str, source: str
) -> zipfile.ZipInfo:
    match = SAFE_PHRASE_RE.fullmatch(phrase_key)
    if match is None:
        raise TavernEventAlignmentError(f"invalid phrase key: {phrase_key}")
    composer, folder, variation, phrase = match.groups()
    prefix = f"{root}/{composer}/{folder}/Encodings/Encoder_{source}/"
    suffix = f"_{variation}_{phrase}_encoder{source}.krn"
    matches = [
        info
        for info in infos
        if not info.is_dir()
        and info.filename.startswith(prefix)
        and info.filename.endswith(suffix)
    ]
    if len(matches) != 1:
        raise TavernEventAlignmentError(
            f"encoder path resolution failed for {phrase_key}/{source}: {len(matches)}"
        )
    return matches[0]


def _joined_member(
    infos: list[zipfile.ZipInfo], *, root: str, phrase_key: str, source: str
) -> zipfile.ZipInfo:
    match = SAFE_PHRASE_RE.fullmatch(phrase_key)
    if match is None:
        raise TavernEventAlignmentError(f"invalid phrase key: {phrase_key}")
    composer, folder, variation, phrase = match.groups()
    prefix = f"{root}/{composer}/{folder}/Joined/"
    matches: list[zipfile.ZipInfo] = []
    for info in infos:
        if info.is_dir() or not info.filename.startswith(prefix):
            continue
        filename = PurePosixPath(info.filename).name
        joined = JOINED_NAME_RE.fullmatch(filename)
        if (
            joined is not None
            and joined.group(1) == variation
            and joined.group(2) == phrase
            and joined.group(3) == source.lower()
        ):
            matches.append(info)
    if len(matches) != 1:
        raise TavernEventAlignmentError(
            f"joined path resolution failed for {phrase_key}/{source}: {len(matches)}"
        )
    return matches[0]


def _event_sequences(
    raw_text: str,
    *,
    accepted_harmonic_spines: tuple[str, ...],
    require_kern_spine: bool,
) -> tuple[list[str | None], list[str]]:
    lines = raw_text.splitlines()
    headers = [
        (index, [cell.strip() for cell in line.split("\t")])
        for index, line in enumerate(lines)
        if line.startswith("**")
    ]
    if len(headers) != 1:
        raise TavernEventAlignmentError(
            f"expected exactly one exclusive-interpretation header, found {len(headers)}"
        )
    header_index, columns = headers[0]
    harmonic_names = [name for name in accepted_harmonic_spines if name in columns]
    if len(harmonic_names) != 1:
        raise TavernEventAlignmentError(
            "expected exactly one accepted harmonic analysis spine"
        )
    if require_kern_spine and "**kern" not in columns:
        raise TavernEventAlignmentError("joined carrier contains no **kern spine")
    harmonic_index = columns.index(harmonic_names[0])

    durations: list[str | None] = []
    labels: list[str] = []
    for line in lines[header_index + 1 :]:
        if not line or line.startswith("!!"):
            continue
        cells = line.split("\t")
        token = cells[harmonic_index].strip() if harmonic_index < len(cells) else ""
        if not token or token.startswith(("*", "=", "!", ".")):
            continue
        reciprocal = RECIPROCAL_PREFIX_RE.match(token)
        if reciprocal is None:
            durations.append(None)
            labels.append(token)
        else:
            durations.append(reciprocal.group(2))
            labels.append(reciprocal.group(1) + reciprocal.group(3))
    if not labels:
        raise TavernEventAlignmentError("analysis contains no harmonic data events")
    return durations, labels


def build_tavern_event_alignment_audit(
    decision_data: object,
    *,
    decision_artifact_sha256: str,
    archive_path: str | Path,
    expected_decision_sha256: str = PINNED_VALIDATED_SHA256,
    expected_archive_sha256: str = PINNED_TAVERN_ARCHIVE_SHA256,
    expected_record_count: int = PINNED_COUNT,
    expected_selected_target_count: int = EXPECTED_SELECTED_TARGET_COUNT,
    expected_alignment_manifest_sha256: str | None = PINNED_ALIGNMENT_MANIFEST_SHA256,
) -> dict[str, object]:
    if decision_artifact_sha256 != expected_decision_sha256:
        raise TavernEventAlignmentError("validated human-decision SHA-256 mismatch")
    if not isinstance(decision_data, dict):
        raise TavernEventAlignmentError("validated decision payload must be an object")
    if decision_data.get("schema_version") != "st-tavern-human-adjudication-v1":
        raise TavernEventAlignmentError("unsupported validated decision schema")
    if decision_data.get("source_corpus") != "TAVERN":
        raise TavernEventAlignmentError("validated decision source corpus mismatch")
    if decision_data.get("source_revision") != PINNED_TAVERN_REVISION:
        raise TavernEventAlignmentError("validated decision source revision mismatch")
    if decision_data.get("reviewer_type") != "HUMAN":
        raise TavernEventAlignmentError("event alignment requires HUMAN decisions")
    decisions = decision_data.get("decisions")
    if not isinstance(decisions, list) or not all(
        isinstance(item, dict) for item in decisions
    ):
        raise TavernEventAlignmentError("validated decisions must be an array of objects")
    if len(decisions) != expected_record_count:
        raise TavernEventAlignmentError("validated decision record count mismatch")

    archive_file = _bounded_regular_file(
        archive_path, max_bytes=MAX_ARCHIVE_BYTES, label="archive"
    )
    archive_sha256 = _sha256_file(archive_file)
    if archive_sha256 != expected_archive_sha256:
        raise TavernEventAlignmentError("TAVERN archive SHA-256 mismatch")

    records: list[dict[str, object]] = []
    stats: Counter[str] = Counter()
    seen_phrases: set[str] = set()
    try:
        with zipfile.ZipFile(archive_file) as archive:
            infos = _validated_zip_members(archive)
            corrupt = archive.testzip()
            if corrupt is not None:
                raise TavernEventAlignmentError(f"corrupt archive member: {corrupt}")
            root = _archive_root(infos)

            for item in decisions:
                phrase_key = item.get("phrase_key")
                if (
                    not isinstance(phrase_key, str)
                    or not phrase_key
                    or phrase_key in seen_phrases
                ):
                    raise TavernEventAlignmentError(
                        "validated phrase keys must be unique non-empty strings"
                    )
                seen_phrases.add(phrase_key)
                decision = item.get("decision")
                sources = _selected_sources(item)
                selected_paths: list[dict[str, object]] = []
                quarantine_reasons: set[str] = set()

                for source in sources:
                    expected_raw_sha256 = item.get(
                        f"annotator_{source}_raw_sha256"
                    )
                    if (
                        not isinstance(expected_raw_sha256, str)
                        or SHA256_RE.fullmatch(expected_raw_sha256) is None
                    ):
                        raise TavernEventAlignmentError(
                            f"malformed selected raw SHA-256 for {phrase_key}/{source}"
                        )
                    encoder_info = _encoder_member(
                        infos, root=root, phrase_key=phrase_key, source=source
                    )
                    encoder_raw = archive.read(encoder_info)
                    if hashlib.sha256(encoder_raw).hexdigest() != expected_raw_sha256:
                        raise TavernEventAlignmentError(
                            f"selected Encoder bytes changed for {phrase_key}/{source}"
                        )
                    joined_info = _joined_member(
                        infos, root=root, phrase_key=phrase_key, source=source
                    )
                    joined_raw = archive.read(joined_info)
                    try:
                        encoder_text = encoder_raw.decode("utf-8", errors="strict")
                        joined_text = joined_raw.decode("utf-8", errors="strict")
                    except UnicodeDecodeError as exc:
                        raise TavernEventAlignmentError(
                            f"alignment source is not UTF-8 for {phrase_key}/{source}"
                        ) from exc

                    try:
                        raw_durations, raw_labels = _event_sequences(
                            encoder_text,
                            accepted_harmonic_spines=("**harm", "**chords"),
                            require_kern_spine=False,
                        )
                        joined_durations, joined_labels = _event_sequences(
                            joined_text,
                            accepted_harmonic_spines=("**harm",),
                            require_kern_spine=True,
                        )
                    except TavernEventAlignmentError as exc:
                        raw_durations = []
                        raw_labels = []
                        joined_durations = []
                        joined_labels = []
                        quarantine_reasons.add(
                            f"{source}_ALIGNMENT_CARRIER_PARSE_FAILED"
                        )
                        parse_error = str(exc)
                    else:
                        parse_error = None

                    missing_duration_count = sum(
                        duration is None for duration in raw_durations
                    )
                    duration_sequence_exact = bool(raw_durations) and (
                        raw_durations == joined_durations
                        and missing_duration_count == 0
                    )
                    if not duration_sequence_exact:
                        quarantine_reasons.add(
                            f"{source}_RECIPROCAL_EVENT_SEQUENCE_MISMATCH"
                        )
                    if missing_duration_count:
                        quarantine_reasons.add(
                            f"{source}_RAW_EVENT_DURATION_MISSING"
                        )
                    joined_label_sequence_exact = bool(raw_labels) and (
                        raw_labels == joined_labels
                    )

                    logical_joined = PurePosixPath(
                        *PurePosixPath(joined_info.filename).parts[1:]
                    ).as_posix()
                    path_evidence: dict[str, object] = {
                        "source": source,
                        "encoder_raw_sha256": expected_raw_sha256,
                        "joined_member": logical_joined,
                        "joined_raw_sha256": hashlib.sha256(joined_raw).hexdigest(),
                        "raw_event_count": len(raw_durations),
                        "joined_event_count": len(joined_durations),
                        "raw_duration_sequence_sha256": _canonical_sha256(
                            raw_durations
                        ),
                        "joined_duration_sequence_sha256": _canonical_sha256(
                            joined_durations
                        ),
                        "duration_sequence_exact": duration_sequence_exact,
                        "raw_missing_duration_count": missing_duration_count,
                        "joined_label_sequence_exact": joined_label_sequence_exact,
                    }
                    if parse_error is not None:
                        path_evidence["parse_error"] = parse_error
                    selected_paths.append(path_evidence)

                    stats["selected_target_count"] += 1
                    stats["duration_sequence_exact_count"] += int(
                        duration_sequence_exact
                    )
                    stats["duration_sequence_mismatch_count"] += int(
                        not duration_sequence_exact
                    )
                    stats["joined_label_sequence_exact_count"] += int(
                        joined_label_sequence_exact
                    )
                    stats["joined_label_sequence_not_exact_count"] += int(
                        not joined_label_sequence_exact
                    )
                    if duration_sequence_exact:
                        stats["aligned_event_path_count"] += len(raw_durations)

                if quarantine_reasons:
                    record_status = "QUARANTINE"
                    stats["quarantine_record_count"] += 1
                elif decision in {"SELECT_A", "SELECT_B"}:
                    record_status = "EXPERT_EVENT_ALIGNMENT_CANDIDATE"
                    stats["event_alignment_candidate_count"] += 1
                    stats["expert_event_alignment_candidate_count"] += 1
                else:
                    record_status = "VARIANT_EVENT_ALIGNMENT_CANDIDATE"
                    stats["event_alignment_candidate_count"] += 1
                    stats["variant_event_alignment_candidate_count"] += 1

                records.append(
                    {
                        "phrase_key": phrase_key,
                        "decision": decision,
                        "record_status": record_status,
                        "selected_paths": selected_paths,
                        "quarantine_reasons": sorted(quarantine_reasons),
                    }
                )
                stats["record_count"] += 1
    except zipfile.BadZipFile as exc:
        raise TavernEventAlignmentError("invalid TAVERN ZIP archive") from exc

    records.sort(key=lambda item: str(item["phrase_key"]))
    if stats["selected_target_count"] != expected_selected_target_count:
        raise TavernEventAlignmentError("selected target count mismatch")
    manifest_sha256 = _canonical_sha256(records)
    if (
        expected_alignment_manifest_sha256 is not None
        and manifest_sha256 != expected_alignment_manifest_sha256
    ):
        raise TavernEventAlignmentError("event-alignment manifest digest changed")

    return {
        "schema_version": ALIGNMENT_SCHEMA,
        "source_corpus": "TAVERN_REVIEWED_694",
        "source_revision": PINNED_TAVERN_REVISION,
        "archive_sha256": archive_sha256,
        "validated_human_decisions_sha256": decision_artifact_sha256,
        "record_count": stats["record_count"],
        "selected_target_count": stats["selected_target_count"],
        "duration_sequence_exact_count": stats["duration_sequence_exact_count"],
        "duration_sequence_mismatch_count": stats[
            "duration_sequence_mismatch_count"
        ],
        "joined_label_sequence_exact_count": stats[
            "joined_label_sequence_exact_count"
        ],
        "joined_label_sequence_not_exact_count": stats[
            "joined_label_sequence_not_exact_count"
        ],
        "event_alignment_candidate_count": stats[
            "event_alignment_candidate_count"
        ],
        "expert_event_alignment_candidate_count": stats[
            "expert_event_alignment_candidate_count"
        ],
        "variant_event_alignment_candidate_count": stats[
            "variant_event_alignment_candidate_count"
        ],
        "quarantine_record_count": stats["quarantine_record_count"],
        "aligned_event_path_count": stats["aligned_event_path_count"],
        "event_alignment_manifest_sha256": manifest_sha256,
        "records": records,
        "joined_role": "SOURCE_DERIVED_ALIGNMENT_CARRIER_ONLY",
        "joined_labels_authoritative": False,
        "joined_labels_used_as_targets": False,
        "event_target_materialization_authorized": False,
        "model_training_started": False,
        "training_authorized": False,
        "production_authority": False,
    }


def build_tavern_event_alignment_audit_from_files(
    decisions_path: str | Path, archive_path: str | Path
) -> dict[str, object]:
    decision_file = _bounded_regular_file(
        decisions_path, max_bytes=1024 * 1024, label="decision artifact"
    )
    raw = decision_file.read_bytes()
    try:
        data = json.loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TavernEventAlignmentError("invalid validated decision JSON") from exc
    return build_tavern_event_alignment_audit(
        data,
        decision_artifact_sha256=hashlib.sha256(raw).hexdigest(),
        archive_path=archive_path,
    )


def build_tavern_event_alignment_summary(data: object) -> dict[str, object]:
    if not isinstance(data, dict) or data.get("schema_version") != ALIGNMENT_SCHEMA:
        raise TavernEventAlignmentError("unsupported event-alignment audit schema")
    if data.get("training_authorized") is not False:
        raise TavernEventAlignmentError("event-alignment audit cannot authorize training")
    fields = (
        "source_corpus",
        "source_revision",
        "archive_sha256",
        "validated_human_decisions_sha256",
        "record_count",
        "selected_target_count",
        "duration_sequence_exact_count",
        "duration_sequence_mismatch_count",
        "joined_label_sequence_exact_count",
        "joined_label_sequence_not_exact_count",
        "event_alignment_candidate_count",
        "expert_event_alignment_candidate_count",
        "variant_event_alignment_candidate_count",
        "quarantine_record_count",
        "aligned_event_path_count",
        "event_alignment_manifest_sha256",
        "joined_role",
        "joined_labels_authoritative",
        "joined_labels_used_as_targets",
        "event_target_materialization_authorized",
        "model_training_started",
        "training_authorized",
        "production_authority",
    )
    result: dict[str, object] = {"schema_version": SUMMARY_SCHEMA}
    result.update({field: data[field] for field in fields})
    return result


def canonical_tavern_event_alignment_json(data: dict[str, object]) -> str:
    if data.get("schema_version") not in {ALIGNMENT_SCHEMA, SUMMARY_SCHEMA}:
        raise TavernEventAlignmentError("unsupported event-alignment schema")
    return json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ) + "\n"
