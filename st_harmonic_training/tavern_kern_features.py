from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import zipfile
from typing import Any

from .tavern_gold_materialization import PINNED_COUNT
from .tavern_raw_label_realization import (
    MAX_ARCHIVE_BYTES,
    PINNED_TAVERN_ARCHIVE_SHA256,
    _bounded_regular_file,
    _validated_zip_members,
)
from .tavern_score_input_realization import (
    SCORE_INPUT_SCHEMA,
    _archive_root,
)
from .tavern_structure import PINNED_TAVERN_REVISION

FEATURE_SCHEMA = "st-tavern-kern-features-v1"
SUMMARY_SCHEMA = "st-tavern-kern-features-summary-v1"
ADAPTER_VERSION = "st-tavern-kern-bow-v1"
PINNED_SCORE_INPUT_MANIFEST_SHA256 = (
    "de394ddcbbb18326b1fc91f162be9fa79eb515cd8e522dab915e79669d42075d"
)
MAX_SCORE_LINES = 5000
MAX_KERN_SPINES = 16
MAX_CELL_TOKEN_CHARS = 256
MAX_FEATURE_KEYS_PER_RECORD = 4096
MAX_FEATURE_OCCURRENCES_PER_RECORD = 20000


class TavernKernFeatureError(ValueError):
    pass


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_kern_bow_features(raw_score_text: str) -> tuple[dict[str, int], dict[str, int]]:
    if not isinstance(raw_score_text, str):
        raise TavernKernFeatureError("score input must be text")
    lines = raw_score_text.splitlines()
    if len(lines) > MAX_SCORE_LINES:
        raise TavernKernFeatureError("score line count exceeds bound")
    headers = [
        (index, line.split("\t"))
        for index, line in enumerate(lines)
        if line.startswith("**")
    ]
    if len(headers) != 1:
        raise TavernKernFeatureError("expected exactly one exclusive-interpretation header")
    header_index, columns = headers[0]
    kern_indices = [index for index, value in enumerate(columns) if value == "**kern"]
    if not kern_indices or len(kern_indices) > MAX_KERN_SPINES:
        raise TavernKernFeatureError("unsupported **kern spine count")

    features: Counter[str] = Counter()
    features[f"SPINE_COUNT::{len(kern_indices)}"] = 1
    stats: Counter[str] = Counter()
    for line in lines[header_index + 1 :]:
        if not line or line.startswith("!!"):
            continue
        stats["processed_row_count"] += 1
        cells = line.split("\t")
        for index in kern_indices:
            token = cells[index].strip() if index < len(cells) else ""
            if not token or token.startswith("!"):
                continue
            if len(token) > MAX_CELL_TOKEN_CHARS:
                raise TavernKernFeatureError("kern cell token exceeds bound")
            if token.startswith("*"):
                features[f"INTERP::{token}"] += 1
                stats["interpretation_token_count"] += 1
            elif token.startswith("="):
                features["BARLINE"] += 1
                stats["barline_token_count"] += 1
            elif token == ".":
                features["NULL"] += 1
                stats["null_token_count"] += 1
            else:
                atoms = token.split()
                if not atoms:
                    raise TavernKernFeatureError("empty data token after split")
                for atom in atoms:
                    if len(atom) > MAX_CELL_TOKEN_CHARS:
                        raise TavernKernFeatureError("kern atom exceeds bound")
                    features[f"KERN_ATOM::{atom}"] += 1
                    stats["kern_atom_count"] += 1

    if len(features) > MAX_FEATURE_KEYS_PER_RECORD:
        raise TavernKernFeatureError("feature key count exceeds bound")
    occurrence_count = sum(features.values())
    if occurrence_count > MAX_FEATURE_OCCURRENCES_PER_RECORD:
        raise TavernKernFeatureError("feature occurrence count exceeds bound")
    if stats["kern_atom_count"] == 0:
        raise TavernKernFeatureError("score contains no kern data atoms")

    return dict(sorted(features.items())), {
        "kern_spine_count": len(kern_indices),
        "processed_row_count": stats["processed_row_count"],
        "kern_atom_count": stats["kern_atom_count"],
        "interpretation_token_count": stats["interpretation_token_count"],
        "barline_token_count": stats["barline_token_count"],
        "null_token_count": stats["null_token_count"],
        "distinct_feature_count": len(features),
        "feature_occurrence_count": occurrence_count,
    }


def build_tavern_kern_features(
    score_realization: object,
    *,
    archive_path: str | Path,
    expected_record_count: int = PINNED_COUNT,
    expected_score_input_manifest_sha256: str = PINNED_SCORE_INPUT_MANIFEST_SHA256,
    expected_archive_sha256: str = PINNED_TAVERN_ARCHIVE_SHA256,
) -> dict[str, object]:
    if not isinstance(score_realization, dict) or score_realization.get("schema_version") != SCORE_INPUT_SCHEMA:
        raise TavernKernFeatureError("unsupported score-input realization schema")
    if score_realization.get("source_corpus") != "TAVERN_REVIEWED_694":
        raise TavernKernFeatureError("source subset mismatch")
    if score_realization.get("source_revision") != PINNED_TAVERN_REVISION:
        raise TavernKernFeatureError("source revision mismatch")
    if score_realization.get("archive_sha256") != expected_archive_sha256:
        raise TavernKernFeatureError("score-input archive digest mismatch")
    if score_realization.get("score_input_manifest_sha256") != expected_score_input_manifest_sha256:
        raise TavernKernFeatureError("score-input manifest digest mismatch")
    if score_realization.get("record_count") != expected_record_count:
        raise TavernKernFeatureError("score-input record count mismatch")
    if score_realization.get("score_input_realization_complete") is not True:
        raise TavernKernFeatureError("score-input realization incomplete")
    if score_realization.get("deterministic_feature_schema_complete") is not False:
        raise TavernKernFeatureError("upstream stage unexpectedly claims feature completion")
    if score_realization.get("training_authorized") is not False:
        raise TavernKernFeatureError("upstream stage cannot authorize training")
    input_records = score_realization.get("records")
    if not isinstance(input_records, list) or not all(isinstance(item, dict) for item in input_records):
        raise TavernKernFeatureError("score-input records malformed")
    if len(input_records) != expected_record_count:
        raise TavernKernFeatureError("score-input payload count mismatch")

    archive_file = _bounded_regular_file(
        archive_path, max_bytes=MAX_ARCHIVE_BYTES, label="archive"
    )
    if _sha256_file(archive_file) != expected_archive_sha256:
        raise TavernKernFeatureError("archive snapshot digest mismatch")

    records: list[dict[str, object]] = []
    global_stats: Counter[str] = Counter()
    vocabulary: set[str] = set()
    distinct_counts: list[int] = []
    occurrence_counts: list[int] = []
    seen_phrases: set[str] = set()
    try:
        with zipfile.ZipFile(archive_file) as archive:
            infos = _validated_zip_members(archive)
            corrupt = archive.testzip()
            if corrupt is not None:
                raise TavernKernFeatureError(f"corrupt archive member: {corrupt}")
            root = _archive_root(infos)
            member_map = {info.filename: info for info in infos if not info.is_dir()}
            for item in input_records:
                phrase_key = item.get("phrase_key")
                score_member = item.get("score_member")
                score_sha256 = item.get("score_sha256")
                if not isinstance(phrase_key, str) or not phrase_key or phrase_key in seen_phrases:
                    raise TavernKernFeatureError("invalid or duplicate phrase key")
                seen_phrases.add(phrase_key)
                if not isinstance(score_member, str) or not score_member:
                    raise TavernKernFeatureError("score member missing")
                if not isinstance(score_sha256, str) or len(score_sha256) != 64:
                    raise TavernKernFeatureError("score SHA-256 malformed")
                archive_name = f"{root}/{score_member}"
                info = member_map.get(archive_name)
                if info is None:
                    raise TavernKernFeatureError(f"score member missing from archive: {phrase_key}")
                raw = archive.read(info)
                if hashlib.sha256(raw).hexdigest() != score_sha256:
                    raise TavernKernFeatureError(f"score bytes changed: {phrase_key}")
                try:
                    text = raw.decode("utf-8", errors="strict")
                except UnicodeDecodeError as exc:
                    raise TavernKernFeatureError(f"score is not UTF-8: {phrase_key}") from exc
                features, stats = extract_kern_bow_features(text)
                feature_bytes = json.dumps(
                    features,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode("utf-8")
                records.append(
                    {
                        "phrase_key": phrase_key,
                        "score_sha256": score_sha256,
                        "features": features,
                        "feature_sha256": hashlib.sha256(feature_bytes).hexdigest(),
                    }
                )
                vocabulary.update(features)
                distinct_counts.append(stats["distinct_feature_count"])
                occurrence_counts.append(stats["feature_occurrence_count"])
                global_stats.update(stats)
    except zipfile.BadZipFile as exc:
        raise TavernKernFeatureError("invalid TAVERN ZIP archive") from exc

    records.sort(key=lambda record: str(record["phrase_key"]))
    manifest_bytes = json.dumps(
        records, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return {
        "schema_version": FEATURE_SCHEMA,
        "adapter_version": ADAPTER_VERSION,
        "source_corpus": "TAVERN_REVIEWED_694",
        "source_revision": PINNED_TAVERN_REVISION,
        "archive_sha256": expected_archive_sha256,
        "score_input_manifest_sha256": expected_score_input_manifest_sha256,
        "record_count": len(records),
        "feature_vocabulary_count": len(vocabulary),
        "feature_occurrence_count": global_stats["feature_occurrence_count"],
        "kern_atom_count": global_stats["kern_atom_count"],
        "processed_row_count": global_stats["processed_row_count"],
        "interpretation_token_count": global_stats["interpretation_token_count"],
        "barline_token_count": global_stats["barline_token_count"],
        "null_token_count": global_stats["null_token_count"],
        "kern_spine_counts": {
            str(count): sum(1 for item in input_records if False)
            for count in ()
        },
        "distinct_feature_per_record_min": min(distinct_counts),
        "distinct_feature_per_record_max": max(distinct_counts),
        "feature_occurrence_per_record_min": min(occurrence_counts),
        "feature_occurrence_per_record_max": max(occurrence_counts),
        "feature_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "records": records,
        "score_input_realization_complete": True,
        "deterministic_feature_schema_complete": True,
        "training_payload_manifest_complete": False,
        "model_training_started": False,
        "training_authorized": False,
    }


def build_tavern_kern_features_summary(data: object) -> dict[str, object]:
    if not isinstance(data, dict) or data.get("schema_version") != FEATURE_SCHEMA:
        raise TavernKernFeatureError("unsupported feature schema")
    if data.get("deterministic_feature_schema_complete") is not True:
        raise TavernKernFeatureError("deterministic feature schema incomplete")
    if data.get("training_authorized") is not False:
        raise TavernKernFeatureError("feature stage cannot authorize training")
    fields = (
        "adapter_version",
        "source_corpus",
        "source_revision",
        "archive_sha256",
        "score_input_manifest_sha256",
        "record_count",
        "feature_vocabulary_count",
        "feature_occurrence_count",
        "kern_atom_count",
        "processed_row_count",
        "interpretation_token_count",
        "barline_token_count",
        "null_token_count",
        "distinct_feature_per_record_min",
        "distinct_feature_per_record_max",
        "feature_occurrence_per_record_min",
        "feature_occurrence_per_record_max",
        "feature_manifest_sha256",
    )
    result: dict[str, object] = {"schema_version": SUMMARY_SCHEMA}
    result.update({field: data[field] for field in fields})
    result.update(
        {
            "score_input_realization_complete": True,
            "deterministic_feature_schema_complete": True,
            "training_payload_manifest_complete": False,
            "model_training_started": False,
            "training_authorized": False,
        }
    )
    return result


def canonical_tavern_kern_feature_json(data: dict[str, object]) -> str:
    if data.get("schema_version") not in {FEATURE_SCHEMA, SUMMARY_SCHEMA}:
        raise TavernKernFeatureError("unsupported feature schema")
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
