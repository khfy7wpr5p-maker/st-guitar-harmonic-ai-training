from __future__ import annotations

from collections import Counter
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import zipfile
from typing import Any

from .normalization import NORMALIZATION_VERSION, build_normalization_record
from .tavern_gold_materialization import PINNED_COUNT, PINNED_VALIDATED_SHA256
from .tavern_raw_label_realization import (
    MAX_ARCHIVE_BYTES,
    PINNED_TAVERN_ARCHIVE_SHA256,
    REALIZATION_SCHEMA,
    _bounded_regular_file,
    _validated_zip_members,
)
from .tavern_structure import PINNED_TAVERN_REVISION

ADAPTER_VERSION = "st-tavern-normalization-adapter-v1"
NORMALIZED_TARGET_SCHEMA = "st-tavern-normalized-targets-v1"
SUMMARY_SCHEMA = "st-tavern-normalized-targets-summary-v1"
EXPECTED_SELECTED_LABEL_COUNT = 747
KEY_RE = re.compile(r"^\*([A-Ga-g](?:[#-]|b)?m?:)$")
RECIPROCAL_PREFIX_RE = re.compile(r"^(\(*)(\d+(?:%\d+)?\.*)(.+)$")


class TavernNormalizationAdapterError(ValueError):
    pass


def _strip_tavern_reciprocal_prefix(token: str) -> str:
    """Remove only TAVERN's explicit leading reciprocal-duration prefix.

    The remaining source token is not semantically rewritten. Unknown harmonic or
    function codes are preserved verbatim.
    """
    match = RECIPROCAL_PREFIX_RE.match(token)
    if match is None:
        return token
    return match.group(1) + match.group(3)


def _json_sequence(values: list[str]) -> str:
    return json.dumps(values, ensure_ascii=False, separators=(",", ":"))


def parse_tavern_analysis_label(
    raw_source_label: str,
) -> tuple[dict[str, str | None], dict[str, object]]:
    if not isinstance(raw_source_label, str):
        raise TavernNormalizationAdapterError("raw TAVERN label must be text")
    lines = raw_source_label.splitlines()
    headers = [
        (index, [cell.strip() for cell in line.split("\t")])
        for index, line in enumerate(lines)
        if line.startswith("**")
    ]
    if len(headers) != 1:
        raise TavernNormalizationAdapterError(
            f"expected exactly one exclusive-interpretation header, found {len(headers)}"
        )
    header_index, columns = headers[0]
    harmonic_names = [name for name in ("**harm", "**chords") if name in columns]
    if len(harmonic_names) != 1:
        raise TavernNormalizationAdapterError(
            "expected exactly one **harm or **chords analysis spine"
        )
    harmonic_name = harmonic_names[0]
    harmonic_index = columns.index(harmonic_name)
    function_indices = [i for i, name in enumerate(columns) if name == "**function"]
    if len(function_indices) > 1:
        raise TavernNormalizationAdapterError("multiple **function spines are unsupported")
    function_index = function_indices[0] if function_indices else None

    explicit_keys: list[str] = []
    harmonic_tokens: list[str] = []
    function_tokens: list[str] = []
    row_width_mismatch_count = 0
    for line in lines[header_index + 1 :]:
        if not line or line.startswith("!!"):
            continue
        cells = line.split("\t")
        if len(cells) != len(columns):
            row_width_mismatch_count += 1

        harmonic = cells[harmonic_index].strip() if harmonic_index < len(cells) else ""
        key_match = KEY_RE.fullmatch(harmonic)
        if key_match is not None:
            explicit_keys.append(key_match.group(1))
        if harmonic and not harmonic.startswith(("*", "=", "!", ".")):
            harmonic_tokens.append(_strip_tavern_reciprocal_prefix(harmonic))

        if function_index is not None:
            function = cells[function_index].strip() if function_index < len(cells) else ""
            if function and not function.startswith(("*", "=", "!", ".")):
                function_tokens.append(_strip_tavern_reciprocal_prefix(function))

    if not harmonic_tokens:
        raise TavernNormalizationAdapterError("TAVERN label has no harmonic data tokens")

    mapping: dict[str, str | None] = {
        "key": explicit_keys[0] if explicit_keys else None,
        "local_key": _json_sequence(explicit_keys[1:]) if len(explicit_keys) > 1 else None,
        "roman_numeral": _json_sequence(harmonic_tokens),
        "bass": None,
        "inversion": None,
        "chord_family": None,
        "extension": None,
        "suspension": None,
        "alteration": None,
        "phrase": _json_sequence(function_tokens) if function_tokens else None,
        "cadence": None,
    }
    metadata: dict[str, object] = {
        "harmonic_spine": harmonic_name,
        "function_spine_present": function_index is not None,
        "explicit_key_count": len(explicit_keys),
        "harmonic_token_count": len(harmonic_tokens),
        "function_token_count": len(function_tokens),
        "row_width_mismatch_count": row_width_mismatch_count,
    }
    return mapping, metadata


def _validate_realization(
    realization: object,
    *,
    expected_record_count: int,
    expected_selected_label_count: int,
    expected_archive_sha256: str,
    expected_decision_sha256: str,
) -> dict[str, Any]:
    if not isinstance(realization, dict) or realization.get("schema_version") != REALIZATION_SCHEMA:
        raise TavernNormalizationAdapterError("unsupported Stage 0-V realization schema")
    if realization.get("source_corpus") != "TAVERN_REVIEWED_694":
        raise TavernNormalizationAdapterError("source subset mismatch")
    if realization.get("source_revision") != PINNED_TAVERN_REVISION:
        raise TavernNormalizationAdapterError("source revision mismatch")
    if realization.get("archive_sha256") != expected_archive_sha256:
        raise TavernNormalizationAdapterError("archive digest mismatch")
    if realization.get("validated_human_decisions_sha256") != expected_decision_sha256:
        raise TavernNormalizationAdapterError("validated human-decision digest mismatch")
    if realization.get("record_count") != expected_record_count:
        raise TavernNormalizationAdapterError("realization record count mismatch")
    if realization.get("selected_label_count") != expected_selected_label_count:
        raise TavernNormalizationAdapterError("selected label count mismatch")
    if realization.get("raw_label_realization_complete") is not True:
        raise TavernNormalizationAdapterError("raw-label realization must be complete")
    if realization.get("normalization_complete") is not False:
        raise TavernNormalizationAdapterError("Stage 0-V must precede normalization")
    if realization.get("training_authorized") is not False:
        raise TavernNormalizationAdapterError("upstream stage cannot authorize training")
    records = realization.get("records")
    if not isinstance(records, list) or not all(isinstance(record, dict) for record in records):
        raise TavernNormalizationAdapterError("realization records are malformed")
    if len(records) != expected_record_count:
        raise TavernNormalizationAdapterError("realization record payload count mismatch")
    return realization


def build_tavern_normalized_targets(
    realization: object,
    *,
    archive_path: str | Path,
    expected_record_count: int = PINNED_COUNT,
    expected_selected_label_count: int = EXPECTED_SELECTED_LABEL_COUNT,
    expected_archive_sha256: str = PINNED_TAVERN_ARCHIVE_SHA256,
    expected_decision_sha256: str = PINNED_VALIDATED_SHA256,
) -> dict[str, object]:
    realized = _validate_realization(
        realization,
        expected_record_count=expected_record_count,
        expected_selected_label_count=expected_selected_label_count,
        expected_archive_sha256=expected_archive_sha256,
        expected_decision_sha256=expected_decision_sha256,
    )
    archive_file = _bounded_regular_file(
        archive_path, max_bytes=MAX_ARCHIVE_BYTES, label="archive"
    )
    archive_bytes = archive_file.read_bytes()
    actual_archive_sha256 = hashlib.sha256(archive_bytes).hexdigest()
    if actual_archive_sha256 != expected_archive_sha256:
        raise TavernNormalizationAdapterError("TAVERN archive snapshot SHA-256 mismatch")

    normalized_records: list[dict[str, object]] = []
    stats: Counter[str] = Counter()
    seen_phrases: set[str] = set()
    try:
        with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
            infos = _validated_zip_members(archive)
            corrupt = archive.testzip()
            if corrupt is not None:
                raise TavernNormalizationAdapterError(f"corrupt archive member: {corrupt}")
            members = {info.filename: info for info in infos}
            for record in realized["records"]:
                phrase_key = record.get("phrase_key")
                decision = record.get("decision")
                selected = record.get("selected_labels")
                if not isinstance(phrase_key, str) or not isinstance(selected, list):
                    raise TavernNormalizationAdapterError("malformed realization record")
                if phrase_key in seen_phrases:
                    raise TavernNormalizationAdapterError(f"duplicate phrase_key: {phrase_key}")
                seen_phrases.add(phrase_key)
                expected_target_count = 2 if decision == "PRESERVE_VARIANTS" else 1
                if decision not in {"SELECT_A", "SELECT_B", "PRESERVE_VARIANTS"}:
                    raise TavernNormalizationAdapterError(
                        f"unsupported realized human decision: {decision}"
                    )
                if len(selected) != expected_target_count:
                    raise TavernNormalizationAdapterError(
                        f"selected target count disagrees with decision: {phrase_key}"
                    )
                targets: list[dict[str, object]] = []
                target_sources: set[str] = set()
                for selected_label in selected:
                    if not isinstance(selected_label, dict):
                        raise TavernNormalizationAdapterError("malformed selected label")
                    source = selected_label.get("source")
                    member_name = selected_label.get("archive_member")
                    raw_sha256 = selected_label.get("raw_sha256")
                    if source not in {"A", "B"} or not isinstance(member_name, str) or not isinstance(raw_sha256, str):
                        raise TavernNormalizationAdapterError("selected label metadata malformed")
                    if source in target_sources:
                        raise TavernNormalizationAdapterError(
                            f"duplicate selected source for phrase: {phrase_key}/{source}"
                        )
                    target_sources.add(source)
                    info = members.get(member_name)
                    if info is None:
                        raise TavernNormalizationAdapterError(
                            f"realized archive member missing: {member_name}"
                        )
                    raw = archive.read(info)
                    if hashlib.sha256(raw).hexdigest() != raw_sha256:
                        raise TavernNormalizationAdapterError(
                            f"realized label changed: {phrase_key}/{source}"
                        )
                    try:
                        raw_text = raw.decode("utf-8", errors="strict")
                    except UnicodeDecodeError as exc:
                        raise TavernNormalizationAdapterError(
                            f"selected label is not UTF-8: {phrase_key}/{source}"
                        ) from exc
                    mapping, metadata = parse_tavern_analysis_label(raw_text)
                    normalization_record = build_normalization_record(
                        raw_text, mapping, normalization_version=NORMALIZATION_VERSION
                    )
                    normalized_label = normalization_record.normalized_st_label.to_dict()
                    normalized_bytes = json.dumps(
                        normalized_label,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=False,
                    ).encode("utf-8")
                    targets.append(
                        {
                            "source": source,
                            "raw_sha256": raw_sha256,
                            "normalized_st_label": normalized_label,
                            "normalized_label_sha256": hashlib.sha256(
                                normalized_bytes
                            ).hexdigest(),
                        }
                    )
                    stats["normalized_target_count"] += 1
                    stats[str(metadata["harmonic_spine"])] += 1
                    if metadata["function_spine_present"]:
                        stats["function_spine_present"] += 1
                    else:
                        stats["function_spine_absent"] += 1
                    if int(metadata["explicit_key_count"]) > 0:
                        stats["explicit_key_present"] += 1
                    if int(metadata["explicit_key_count"]) > 1:
                        stats["key_change_sequence_present"] += 1
                    if int(metadata["row_width_mismatch_count"]) > 0:
                        stats["row_width_mismatch_file_count"] += 1
                    stats["row_width_mismatch_count"] += int(
                        metadata["row_width_mismatch_count"]
                    )
                    stats["harmonic_token_count"] += int(metadata["harmonic_token_count"])
                    stats["function_token_count"] += int(metadata["function_token_count"])
                if decision == "SELECT_A" and target_sources != {"A"}:
                    raise TavernNormalizationAdapterError("SELECT_A source mismatch")
                if decision == "SELECT_B" and target_sources != {"B"}:
                    raise TavernNormalizationAdapterError("SELECT_B source mismatch")
                if decision == "PRESERVE_VARIANTS" and target_sources != {"A", "B"}:
                    raise TavernNormalizationAdapterError("variant source set mismatch")
                normalized_records.append(
                    {
                        "phrase_key": phrase_key,
                        "decision": decision,
                        "targets": sorted(targets, key=lambda target: str(target["source"])),
                    }
                )
    except zipfile.BadZipFile as exc:
        raise TavernNormalizationAdapterError("invalid TAVERN ZIP archive") from exc

    normalized_records.sort(key=lambda record: str(record["phrase_key"]))
    if len(normalized_records) != expected_record_count:
        raise TavernNormalizationAdapterError("normalized record count mismatch")
    if stats["normalized_target_count"] != expected_selected_label_count:
        raise TavernNormalizationAdapterError("normalized target count mismatch")
    manifest_bytes = json.dumps(
        normalized_records,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return {
        "schema_version": NORMALIZED_TARGET_SCHEMA,
        "adapter_version": ADAPTER_VERSION,
        "normalization_version": NORMALIZATION_VERSION,
        "source_corpus": "TAVERN_REVIEWED_694",
        "source_revision": PINNED_TAVERN_REVISION,
        "archive_sha256": actual_archive_sha256,
        "validated_human_decisions_sha256": realized[
            "validated_human_decisions_sha256"
        ],
        "record_count": len(normalized_records),
        "normalized_target_count": stats["normalized_target_count"],
        "harmonic_spine_counts": {
            "**chords": stats["**chords"],
            "**harm": stats["**harm"],
        },
        "function_spine_present_count": stats["function_spine_present"],
        "function_spine_absent_count": stats["function_spine_absent"],
        "explicit_key_present_count": stats["explicit_key_present"],
        "key_change_sequence_present_count": stats["key_change_sequence_present"],
        "row_width_mismatch_file_count": stats["row_width_mismatch_file_count"],
        "row_width_mismatch_count": stats["row_width_mismatch_count"],
        "harmonic_token_count": stats["harmonic_token_count"],
        "function_token_count": stats["function_token_count"],
        "normalized_target_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "records": normalized_records,
        "raw_label_realization_complete": True,
        "normalization_complete": True,
        "partition_assignment_authorized": False,
        "training_authorized": False,
    }


def build_tavern_normalized_targets_summary(data: object) -> dict[str, object]:
    if not isinstance(data, dict) or data.get("schema_version") != NORMALIZED_TARGET_SCHEMA:
        raise TavernNormalizationAdapterError("unsupported normalized target schema")
    if data.get("normalization_complete") is not True:
        raise TavernNormalizationAdapterError("normalization is not complete")
    if data.get("training_authorized") is not False:
        raise TavernNormalizationAdapterError("normalization cannot authorize training")
    fields = (
        "adapter_version",
        "normalization_version",
        "source_corpus",
        "source_revision",
        "archive_sha256",
        "validated_human_decisions_sha256",
        "record_count",
        "normalized_target_count",
        "harmonic_spine_counts",
        "function_spine_present_count",
        "function_spine_absent_count",
        "explicit_key_present_count",
        "key_change_sequence_present_count",
        "row_width_mismatch_file_count",
        "row_width_mismatch_count",
        "harmonic_token_count",
        "function_token_count",
        "normalized_target_manifest_sha256",
    )
    result: dict[str, object] = {"schema_version": SUMMARY_SCHEMA}
    result.update({field: data[field] for field in fields})
    result.update(
        {
            "raw_label_realization_complete": True,
            "normalization_complete": True,
            "partition_assignment_authorized": False,
            "training_authorized": False,
        }
    )
    return result


def canonical_tavern_normalized_targets_json(data: dict[str, object]) -> str:
    if data.get("schema_version") not in {NORMALIZED_TARGET_SCHEMA, SUMMARY_SCHEMA}:
        raise TavernNormalizationAdapterError("unsupported normalized target schema")
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
