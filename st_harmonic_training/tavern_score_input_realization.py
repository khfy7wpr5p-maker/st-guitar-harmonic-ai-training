from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile
from typing import Any

from .tavern_adjudication import ADJUDICATION_INPUT_SCHEMA
from .tavern_gold_materialization import PINNED_COUNT, PINNED_VALIDATED_SHA256
from .tavern_raw_label_realization import (
    MAX_ARCHIVE_BYTES,
    PINNED_TAVERN_ARCHIVE_SHA256,
    _bounded_regular_file,
    _validated_zip_members,
)
from .tavern_structure import PINNED_TAVERN_REVISION
from .tavern_subset_admission import SCORE_SHA256

SCORE_INPUT_SCHEMA = "st-tavern-score-input-realization-v1"
SUMMARY_SCHEMA = "st-tavern-score-input-realization-summary-v1"
INVENTORY_SCHEMA = "st-corpus-inventory-v1"
MAX_DECISION_BYTES = 1024 * 1024
MAX_SCORE_BYTES = 2 * 1024 * 1024
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PHRASE_RE = re.compile(r"^(Beethoven|Mozart)/([A-Za-z0-9]+):(\d{2}):(\d{2})$")


class TavernScoreInputRealizationError(ValueError):
    pass


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _archive_root(infos: list[zipfile.ZipInfo]) -> str:
    roots: set[str] = set()
    for info in infos:
        parts = PurePosixPath(info.filename.replace("\\", "/")).parts
        if parts:
            roots.add(parts[0])
    if len(roots) != 1:
        raise TavernScoreInputRealizationError("archive must contain one top-level root")
    root = next(iter(roots))
    if not root.startswith("TAVERN-"):
        raise TavernScoreInputRealizationError("unexpected TAVERN archive root")
    return root


def _logical_path(name: str, root: str) -> str:
    parts = PurePosixPath(name.replace("\\", "/")).parts
    if not parts or parts[0] != root:
        raise TavernScoreInputRealizationError("archive member outside root")
    return PurePosixPath(*parts[1:]).as_posix() if len(parts) > 1 else ""


def _score_inventory_digest(
    archive: zipfile.ZipFile,
    infos: list[zipfile.ZipInfo],
    *,
    root: str,
    source_corpus: str = "TAVERN",
    immutable_revision: str = PINNED_TAVERN_REVISION,
) -> tuple[str, int]:
    entries: list[dict[str, object]] = []
    for info in sorted(infos, key=lambda item: _logical_path(item.filename, root)):
        if info.is_dir():
            continue
        logical = _logical_path(info.filename, root)
        path = PurePosixPath(logical)
        parts = path.parts
        if (
            path.suffix.lower() != ".krn"
            or len(parts) < 4
            or parts[0] not in {"Beethoven", "Mozart"}
            or parts[2] != "Krn"
        ):
            continue
        raw = archive.read(info)
        if len(raw) != info.file_size:
            raise TavernScoreInputRealizationError("score inventory member size mismatch")
        entries.append(
            {
                "path": logical,
                "size_bytes": info.file_size,
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    if not entries:
        raise TavernScoreInputRealizationError("score inventory is empty")
    payload = {
        "schema_version": INVENTORY_SCHEMA,
        "source_corpus": source_corpus,
        "immutable_revision": immutable_revision,
        "role": "score",
        "entries": entries,
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ) + "\n"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest(), len(entries)


def _score_member(
    infos: list[zipfile.ZipInfo],
    *,
    root: str,
    phrase_key: str,
) -> zipfile.ZipInfo:
    match = PHRASE_RE.fullmatch(phrase_key)
    if match is None:
        raise TavernScoreInputRealizationError(f"invalid phrase key: {phrase_key}")
    composer, folder, variation, phrase = match.groups()
    prefix = f"{root}/{composer}/{folder}/Krn/"
    suffixes = (
        f"_{variation}_{phrase}_score.krn",
        f"_V{variation}_{phrase}_score.krn",
    )
    matches = [
        info
        for info in infos
        if not info.is_dir()
        and info.filename.startswith(prefix)
        and any(info.filename.endswith(suffix) for suffix in suffixes)
    ]
    if len(matches) != 1:
        raise TavernScoreInputRealizationError(
            f"score path resolution failed for {phrase_key}: {len(matches)} matches"
        )
    return matches[0]


def build_tavern_score_input_realization(
    decision_data: object,
    *,
    decision_artifact_sha256: str,
    archive_path: str | Path,
    expected_decision_sha256: str = PINNED_VALIDATED_SHA256,
    expected_archive_sha256: str = PINNED_TAVERN_ARCHIVE_SHA256,
    expected_score_inventory_sha256: str = SCORE_SHA256,
    expected_count: int = PINNED_COUNT,
) -> dict[str, object]:
    if decision_artifact_sha256 != expected_decision_sha256:
        raise TavernScoreInputRealizationError("validated decision artifact SHA-256 mismatch")
    if not isinstance(decision_data, dict) or decision_data.get("schema_version") != ADJUDICATION_INPUT_SCHEMA:
        raise TavernScoreInputRealizationError("unsupported decision schema")
    if decision_data.get("source_corpus") != "TAVERN":
        raise TavernScoreInputRealizationError("source corpus mismatch")
    if decision_data.get("source_revision") != PINNED_TAVERN_REVISION:
        raise TavernScoreInputRealizationError("source revision mismatch")
    if decision_data.get("reviewer_type") != "HUMAN":
        raise TavernScoreInputRealizationError("human reviewer required")
    decisions = decision_data.get("decisions")
    if not isinstance(decisions, list) or not all(isinstance(item, dict) for item in decisions):
        raise TavernScoreInputRealizationError("decisions must be an array of objects")
    if len(decisions) != expected_count:
        raise TavernScoreInputRealizationError("decision count mismatch")
    if SHA256_RE.fullmatch(expected_score_inventory_sha256) is None:
        raise TavernScoreInputRealizationError("expected score inventory digest malformed")

    archive_file = _bounded_regular_file(
        archive_path, max_bytes=MAX_ARCHIVE_BYTES, label="archive"
    )
    observed_archive_sha256 = _sha256_file(archive_file)
    if observed_archive_sha256 != expected_archive_sha256:
        raise TavernScoreInputRealizationError("TAVERN archive SHA-256 mismatch")

    records: list[dict[str, object]] = []
    seen: set[str] = set()
    score_byte_count = 0
    try:
        with zipfile.ZipFile(archive_file) as archive:
            infos = _validated_zip_members(archive)
            corrupt = archive.testzip()
            if corrupt is not None:
                raise TavernScoreInputRealizationError(f"corrupt archive member: {corrupt}")
            root = _archive_root(infos)
            inventory_sha256, inventory_count = _score_inventory_digest(
                archive, infos, root=root
            )
            if inventory_sha256 != expected_score_inventory_sha256:
                raise TavernScoreInputRealizationError("TAVERN score inventory SHA-256 mismatch")

            for item in decisions:
                phrase_key = item.get("phrase_key")
                if not isinstance(phrase_key, str) or not phrase_key:
                    raise TavernScoreInputRealizationError("decision missing phrase key")
                if phrase_key in seen:
                    raise TavernScoreInputRealizationError(f"duplicate phrase key: {phrase_key}")
                seen.add(phrase_key)
                info = _score_member(infos, root=root, phrase_key=phrase_key)
                if info.file_size > MAX_SCORE_BYTES:
                    raise TavernScoreInputRealizationError("score phrase exceeds size bound")
                raw = archive.read(info)
                if len(raw) != info.file_size:
                    raise TavernScoreInputRealizationError("score phrase size mismatch")
                try:
                    text = raw.decode("utf-8", errors="strict")
                except UnicodeDecodeError as exc:
                    raise TavernScoreInputRealizationError(
                        f"score phrase is not UTF-8: {phrase_key}"
                    ) from exc
                headers = [line for line in text.splitlines() if line.startswith("**")]
                if len(headers) != 1 or "**kern" not in headers[0].split("\t"):
                    raise TavernScoreInputRealizationError(
                        f"score phrase lacks one valid **kern header: {phrase_key}"
                    )
                logical = _logical_path(info.filename, root)
                records.append(
                    {
                        "phrase_key": phrase_key,
                        "score_member": logical,
                        "score_sha256": hashlib.sha256(raw).hexdigest(),
                        "byte_count": len(raw),
                    }
                )
                score_byte_count += len(raw)
    except zipfile.BadZipFile as exc:
        raise TavernScoreInputRealizationError("invalid TAVERN ZIP archive") from exc

    records.sort(key=lambda record: str(record["phrase_key"]))
    manifest_bytes = json.dumps(
        records, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return {
        "schema_version": SCORE_INPUT_SCHEMA,
        "source_corpus": "TAVERN_REVIEWED_694",
        "source_revision": PINNED_TAVERN_REVISION,
        "archive_sha256": observed_archive_sha256,
        "score_inventory_sha256": expected_score_inventory_sha256,
        "score_inventory_member_count": inventory_count,
        "validated_human_decisions_sha256": decision_artifact_sha256,
        "record_count": len(records),
        "score_input_count": len(records),
        "score_input_byte_count": score_byte_count,
        "score_input_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "records": records,
        "score_input_realization_complete": True,
        "deterministic_feature_schema_complete": False,
        "training_payload_manifest_complete": False,
        "model_training_started": False,
        "training_authorized": False,
    }


def build_tavern_score_input_realization_from_files(
    decisions_path: str | Path,
    archive_path: str | Path,
) -> dict[str, object]:
    decision_file = _bounded_regular_file(
        decisions_path, max_bytes=MAX_DECISION_BYTES, label="validated decisions"
    )
    raw = decision_file.read_bytes()
    if len(raw) > MAX_DECISION_BYTES:
        raise TavernScoreInputRealizationError("decision input exceeds size bound")
    try:
        data = json.loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TavernScoreInputRealizationError("invalid decision JSON") from exc
    return build_tavern_score_input_realization(
        data,
        decision_artifact_sha256=hashlib.sha256(raw).hexdigest(),
        archive_path=archive_path,
    )


def build_tavern_score_input_realization_summary(data: object) -> dict[str, object]:
    if not isinstance(data, dict) or data.get("schema_version") != SCORE_INPUT_SCHEMA:
        raise TavernScoreInputRealizationError("unsupported score input realization schema")
    if data.get("score_input_realization_complete") is not True:
        raise TavernScoreInputRealizationError("score input realization incomplete")
    if data.get("training_authorized") is not False:
        raise TavernScoreInputRealizationError("score input realization cannot authorize training")
    fields = (
        "source_corpus",
        "source_revision",
        "archive_sha256",
        "score_inventory_sha256",
        "score_inventory_member_count",
        "validated_human_decisions_sha256",
        "record_count",
        "score_input_count",
        "score_input_byte_count",
        "score_input_manifest_sha256",
    )
    result: dict[str, object] = {"schema_version": SUMMARY_SCHEMA}
    result.update({field: data[field] for field in fields})
    result.update(
        {
            "score_input_realization_complete": True,
            "deterministic_feature_schema_complete": False,
            "training_payload_manifest_complete": False,
            "model_training_started": False,
            "training_authorized": False,
        }
    )
    return result


def canonical_tavern_score_input_json(data: dict[str, object]) -> str:
    if data.get("schema_version") not in {SCORE_INPUT_SCHEMA, SUMMARY_SCHEMA}:
        raise TavernScoreInputRealizationError("unsupported score input schema")
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
