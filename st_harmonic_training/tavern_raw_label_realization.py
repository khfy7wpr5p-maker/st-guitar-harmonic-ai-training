from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile
from typing import Any

from .tavern_adjudication import ADJUDICATION_INPUT_SCHEMA
from .tavern_gold_materialization import PINNED_COUNT, PINNED_VALIDATED_SHA256
from .tavern_structure import PINNED_TAVERN_REVISION

REALIZATION_SCHEMA = "st-tavern-raw-label-realization-v1"
SUMMARY_SCHEMA = "st-tavern-raw-label-realization-summary-v1"
PINNED_TAVERN_ARCHIVE_SHA256 = "b95d85bb3f1e5c0f4ea6df772928d247243485abd93153f0550d6be2fba4fc63"
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 10_000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 256 * 1024 * 1024
MAX_LABEL_BYTES = 1024 * 1024
MAX_DECISION_BYTES = 1024 * 1024
SAFE_PHRASE_RE = re.compile(r"^(Beethoven|Mozart)/([A-Za-z0-9]+):(\d{2}):(\d{2})$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class TavernRawLabelRealizationError(ValueError):
    pass


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bounded_regular_file(path: str | Path, *, max_bytes: int, label: str) -> Path:
    candidate = Path(path)
    if candidate.is_symlink():
        raise TavernRawLabelRealizationError(f"{label} symlink rejected")
    meta = candidate.stat()
    if not stat.S_ISREG(meta.st_mode):
        raise TavernRawLabelRealizationError(f"{label} must be a regular file")
    if meta.st_size > max_bytes:
        raise TavernRawLabelRealizationError(f"{label} exceeds size bound")
    return candidate


def _validated_zip_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    infos = archive.infolist()
    if len(infos) > MAX_ARCHIVE_MEMBERS:
        raise TavernRawLabelRealizationError("archive member count exceeds bound")
    names: set[str] = set()
    total = 0
    for info in infos:
        name = info.filename
        if name in names:
            raise TavernRawLabelRealizationError(f"duplicate archive member: {name}")
        names.add(name)
        path = PurePosixPath(name.replace("\\", "/"))
        if path.is_absolute() or any(part in {".", ".."} for part in path.parts):
            raise TavernRawLabelRealizationError(f"unsafe archive path: {name}")
        mode = (info.external_attr >> 16) & 0xFFFF
        if stat.S_ISLNK(mode):
            raise TavernRawLabelRealizationError(f"archive symlink rejected: {name}")
        total += info.file_size
        if total > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
            raise TavernRawLabelRealizationError("archive uncompressed size exceeds bound")
    return infos


def _selected_sources(item: dict[str, Any]) -> list[tuple[str, str]]:
    decision = item.get("decision")
    if decision == "SELECT_A":
        return [("A", str(item.get("annotator_A_raw_sha256", "")))]
    if decision == "SELECT_B":
        return [("B", str(item.get("annotator_B_raw_sha256", "")))]
    if decision == "PRESERVE_VARIANTS":
        return [
            ("A", str(item.get("annotator_A_raw_sha256", ""))),
            ("B", str(item.get("annotator_B_raw_sha256", ""))),
        ]
    raise TavernRawLabelRealizationError(f"unsupported validated decision: {decision}")


def _selected_member(
    infos: list[zipfile.ZipInfo], phrase_key: str, source: str
) -> zipfile.ZipInfo:
    match = SAFE_PHRASE_RE.fullmatch(phrase_key)
    if match is None:
        raise TavernRawLabelRealizationError(f"invalid phrase_key: {phrase_key}")
    composer, folder, variation, phrase = match.groups()
    prefix = f"TAVERN-master/{composer}/{folder}/Encodings/Encoder_{source}/"
    suffix = f"_{variation}_{phrase}_encoder{source}.krn"
    matches = [
        info
        for info in infos
        if info.filename.startswith(prefix) and info.filename.endswith(suffix)
    ]
    if len(matches) != 1:
        raise TavernRawLabelRealizationError(
            f"selected label path resolution failed for {phrase_key}/{source}: "
            f"{len(matches)} matches"
        )
    return matches[0]


def build_tavern_raw_label_realization(
    decision_data: object,
    *,
    decision_artifact_sha256: str,
    archive_path: str | Path,
    expected_decision_sha256: str = PINNED_VALIDATED_SHA256,
    expected_archive_sha256: str = PINNED_TAVERN_ARCHIVE_SHA256,
    expected_count: int = PINNED_COUNT,
) -> dict[str, object]:
    if decision_artifact_sha256 != expected_decision_sha256:
        raise TavernRawLabelRealizationError("validated decision artifact SHA-256 mismatch")
    if not isinstance(decision_data, dict) or decision_data.get("schema_version") != ADJUDICATION_INPUT_SCHEMA:
        raise TavernRawLabelRealizationError("unsupported decision schema")
    if decision_data.get("source_corpus") != "TAVERN" or decision_data.get("source_revision") != PINNED_TAVERN_REVISION:
        raise TavernRawLabelRealizationError("source identity mismatch")
    if decision_data.get("reviewer_type") != "HUMAN":
        raise TavernRawLabelRealizationError("human reviewer required")
    decisions = decision_data.get("decisions")
    if not isinstance(decisions, list) or not all(isinstance(item, dict) for item in decisions):
        raise TavernRawLabelRealizationError("decisions must be an array of objects")
    if len(decisions) != expected_count:
        raise TavernRawLabelRealizationError("validated decision count mismatch")

    archive_file = _bounded_regular_file(archive_path, max_bytes=MAX_ARCHIVE_BYTES, label="archive")
    archive_sha256 = _sha256_file(archive_file)
    if archive_sha256 != expected_archive_sha256:
        raise TavernRawLabelRealizationError("TAVERN archive SHA-256 mismatch")

    records: list[dict[str, object]] = []
    seen_phrases: set[str] = set()
    source_counts: Counter[str] = Counter()
    selected_label_count = 0
    selected_raw_byte_count = 0
    try:
        with zipfile.ZipFile(archive_file) as archive:
            infos = _validated_zip_members(archive)
            corrupt = archive.testzip()
            if corrupt is not None:
                raise TavernRawLabelRealizationError(f"corrupt archive member: {corrupt}")
            for item in decisions:
                phrase_key = item.get("phrase_key")
                if not isinstance(phrase_key, str) or not phrase_key:
                    raise TavernRawLabelRealizationError("decision missing phrase_key")
                if phrase_key in seen_phrases:
                    raise TavernRawLabelRealizationError(f"duplicate phrase_key: {phrase_key}")
                seen_phrases.add(phrase_key)
                selected_labels: list[dict[str, object]] = []
                for source, expected_hash in _selected_sources(item):
                    if SHA256_RE.fullmatch(expected_hash) is None:
                        raise TavernRawLabelRealizationError(
                            f"invalid selected SHA-256 for {phrase_key}/{source}"
                        )
                    info = _selected_member(infos, phrase_key, source)
                    if info.file_size > MAX_LABEL_BYTES:
                        raise TavernRawLabelRealizationError(
                            f"selected label exceeds size bound: {info.filename}"
                        )
                    raw = archive.read(info)
                    actual_hash = hashlib.sha256(raw).hexdigest()
                    if actual_hash != expected_hash:
                        raise TavernRawLabelRealizationError(
                            f"selected label SHA-256 mismatch: {phrase_key}/{source}"
                        )
                    try:
                        raw.decode("utf-8", errors="strict")
                    except UnicodeDecodeError as exc:
                        raise TavernRawLabelRealizationError(
                            f"selected label is not UTF-8: {phrase_key}/{source}"
                        ) from exc
                    selected_labels.append(
                        {
                            "source": source,
                            "archive_member": info.filename,
                            "raw_sha256": actual_hash,
                            "byte_count": len(raw),
                        }
                    )
                    source_counts[source] += 1
                    selected_label_count += 1
                    selected_raw_byte_count += len(raw)
                records.append(
                    {
                        "phrase_key": phrase_key,
                        "decision": item.get("decision"),
                        "selected_labels": selected_labels,
                    }
                )
    except zipfile.BadZipFile as exc:
        raise TavernRawLabelRealizationError("invalid TAVERN ZIP archive") from exc

    records.sort(key=lambda record: str(record["phrase_key"]))
    manifest_bytes = json.dumps(
        records, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return {
        "schema_version": REALIZATION_SCHEMA,
        "source_corpus": "TAVERN_REVIEWED_694",
        "source_revision": PINNED_TAVERN_REVISION,
        "archive_sha256": archive_sha256,
        "validated_human_decisions_sha256": decision_artifact_sha256,
        "record_count": len(records),
        "selected_label_count": selected_label_count,
        "selected_source_counts": {
            key: source_counts[key] for key in sorted(source_counts)
        },
        "selected_raw_byte_count": selected_raw_byte_count,
        "realization_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "records": records,
        "raw_label_realization_complete": True,
        "normalization_complete": False,
        "training_authorized": False,
    }


def build_tavern_raw_label_realization_from_files(
    decisions_path: str | Path, archive_path: str | Path
) -> dict[str, object]:
    decision_file = _bounded_regular_file(
        decisions_path, max_bytes=MAX_DECISION_BYTES, label="decision artifact"
    )
    raw = decision_file.read_bytes()
    try:
        data = json.loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TavernRawLabelRealizationError("invalid validated decision JSON") from exc
    return build_tavern_raw_label_realization(
        data,
        decision_artifact_sha256=hashlib.sha256(raw).hexdigest(),
        archive_path=archive_path,
    )


def build_tavern_raw_label_realization_summary(
    realization: object,
) -> dict[str, object]:
    if not isinstance(realization, dict) or realization.get("schema_version") != REALIZATION_SCHEMA:
        raise TavernRawLabelRealizationError("unsupported realization schema")
    if realization.get("raw_label_realization_complete") is not True:
        raise TavernRawLabelRealizationError("raw-label realization is not complete")
    if realization.get("training_authorized") is not False:
        raise TavernRawLabelRealizationError("raw-label realization cannot authorize training")
    return {
        "schema_version": SUMMARY_SCHEMA,
        "source_corpus": realization["source_corpus"],
        "source_revision": realization["source_revision"],
        "archive_sha256": realization["archive_sha256"],
        "validated_human_decisions_sha256": realization[
            "validated_human_decisions_sha256"
        ],
        "record_count": realization["record_count"],
        "selected_label_count": realization["selected_label_count"],
        "selected_source_counts": realization["selected_source_counts"],
        "selected_raw_byte_count": realization["selected_raw_byte_count"],
        "realization_manifest_sha256": realization["realization_manifest_sha256"],
        "raw_label_realization_complete": True,
        "normalization_complete": False,
        "training_authorized": False,
    }


def canonical_tavern_raw_label_realization_json(data: dict[str, object]) -> str:
    if data.get("schema_version") not in {REALIZATION_SCHEMA, SUMMARY_SCHEMA}:
        raise TavernRawLabelRealizationError("unsupported realization schema")
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
