"""Stage 2-R TRAIN-only dynamic Humdrum spine topology feasibility audit.

Audit-only. This stage measures source topology around the Stage 2-Q exact
alignment blockers. It does not implement dynamic-spine materialization, infer
musical timing, inspect Function target values, or fit a model.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import zipfile
from typing import Any

from .offline_experiment import require_locked_runtime
from .safe_ingest import load_bounded_json
from .stage2h_function_event_cv import (
    EXPECTED_STAGE2G_EVENT_COUNT,
    EXPECTED_STAGE2G_MATERIALIZABLE_SOURCE_PATH_COUNT,
    EXPECTED_STAGE2G_PRIVATE_EVENT_MANIFEST_SHA256,
    MAX_PRIVATE_BYTES,
    _validate_stage2g_private_payload,
)
from .tavern_event_alignment_audit import _joined_member
from .tavern_raw_label_realization import (
    MAX_ARCHIVE_BYTES,
    PINNED_TAVERN_ARCHIVE_SHA256,
    _bounded_regular_file,
    _validated_zip_members,
)
from .tavern_score_input_realization import MAX_SCORE_BYTES, _archive_root, _score_member

CONTRACT_SCHEMA = "st-stage2r-dynamic-spine-feasibility-contract-v1"
SUMMARY_SCHEMA = "st-stage2r-dynamic-spine-feasibility-summary-v1"
SOURCE_CORPUS = "TAVERN_REVIEWED_694"
EXPECTED_TRAINING_BASE_SHA = "51ea94008514889f4fe41c881d9c3c02f3d61ce0"
OBSERVED_DYNAMIC_TOKENS = ("*^", "*v", "*x", "*+")
MAX_SOURCE_LINES = 5000
MAX_COLUMNS = 32


class Stage2RDynamicSpineAuditError(ValueError):
    pass


def build_stage2r_contract() -> dict[str, object]:
    return {
        "schema_version": CONTRACT_SCHEMA,
        "stage": "STAGE_2_R",
        "audit_only": True,
        "source_training_main_sha": EXPECTED_TRAINING_BASE_SHA,
        "source_corpus": SOURCE_CORPUS,
        "eligible_original_partition": "TRAIN",
        "source_stage2g_private_event_manifest_sha256": EXPECTED_STAGE2G_PRIVATE_EVENT_MANIFEST_SHA256,
        "source_stage2g_materialized_event_count": EXPECTED_STAGE2G_EVENT_COUNT,
        "source_stage2g_materializable_source_path_count": EXPECTED_STAGE2G_MATERIALIZABLE_SOURCE_PATH_COUNT,
        "source_tavern_archive_sha256": PINNED_TAVERN_ARCHIVE_SHA256,
        "audited_spine_path_tokens": list(OBSERVED_DYNAMIC_TOKENS),
        "dynamic_spine_materialization_authorized": False,
        "timing_inference_authorized": False,
        "function_target_value_access_for_topology": False,
        "joined_harmonic_label_value_access_for_topology": False,
        "model_feature_materialization_authorized": False,
        "model_training_started": False,
        "model_selection_started": False,
        "non_train_access_authorized": False,
        "production_authority": False,
        "deterministic_resolver_remains_authoritative": True,
    }


def validate_stage2r_contract(data: object) -> dict[str, object]:
    expected = build_stage2r_contract()
    if not isinstance(data, dict) or data != expected:
        raise Stage2RDynamicSpineAuditError("Stage 2-R contract differs from frozen audit contract")
    return data


def scan_spine_topology(raw_text: str, *, source_kind: str) -> dict[str, object]:
    if not isinstance(raw_text, str):
        raise TypeError("raw_text must be text")
    if source_kind not in {"SCORE", "JOINED"}:
        raise Stage2RDynamicSpineAuditError("source_kind must be SCORE or JOINED")
    lines = raw_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if len(lines) > MAX_SOURCE_LINES:
        raise Stage2RDynamicSpineAuditError("source line count exceeds bound")
    headers = [line.split("\t") for line in lines if line.startswith("**")]
    if len(headers) != 1:
        raise Stage2RDynamicSpineAuditError("expected exactly one exclusive header")
    header = headers[0]
    if len(header) > MAX_COLUMNS:
        raise Stage2RDynamicSpineAuditError("exclusive header exceeds column bound")
    if source_kind == "SCORE":
        if not header or any(value != "**kern" for value in header):
            raise Stage2RDynamicSpineAuditError("score topology audit requires only **kern spines")
        non_kern_fixed_columns = 0
    else:
        if header.count("**harm") != 1 or header.count("**function") > 1:
            raise Stage2RDynamicSpineAuditError("Joined topology requires one **harm and at most one **function")
        if header.count("**kern") < 1:
            raise Stage2RDynamicSpineAuditError("Joined topology has no **kern spine")
        if any(value not in {"**kern", "**harm", "**function"} for value in header):
            raise Stage2RDynamicSpineAuditError("Joined topology contains unsupported spine type")
        non_kern_fixed_columns = len(header) - header.count("**kern")

    operation_occurrences: Counter[str] = Counter()
    min_width = len(header)
    max_width = len(header)
    for line in lines:
        if not line or line.startswith("!!"):
            continue
        cells = line.split("\t")
        if len(cells) > MAX_COLUMNS:
            raise Stage2RDynamicSpineAuditError("source row exceeds column bound")
        min_width = min(min_width, len(cells))
        max_width = max(max_width, len(cells))
        for cell in cells:
            if cell in OBSERVED_DYNAMIC_TOKENS:
                operation_occurrences[cell] += 1

    initial_kern_spine_count = header.count("**kern")
    max_observed_kern_spine_count = max_width - non_kern_fixed_columns
    if max_observed_kern_spine_count < initial_kern_spine_count:
        raise Stage2RDynamicSpineAuditError("observed width is incompatible with initial kern spine count")
    return {
        "source_kind": source_kind,
        "initial_kern_spine_count": initial_kern_spine_count,
        "max_observed_kern_spine_count": max_observed_kern_spine_count,
        "min_row_width": min_width,
        "max_row_width": max_width,
        "operation_occurrences": {token: operation_occurrences[token] for token in OBSERVED_DYNAMIC_TOKENS},
        "dynamic_path_present": any(operation_occurrences.values()),
        "split_present": operation_occurrences["*^"] > 0,
        "join_present": operation_occurrences["*v"] > 0,
        "exchange_present": operation_occurrences["*x"] > 0,
        "add_present": operation_occurrences["*+"] > 0,
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_stage2r_audit(stage2g_data: object, *, archive_path: str | Path) -> dict[str, object]:
    validate_stage2r_contract(build_stage2r_contract())
    events = _validate_stage2g_private_payload(stage2g_data)
    paths: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        if not isinstance(event, dict):
            raise Stage2RDynamicSpineAuditError("Stage2G event row malformed")
        phrase = event.get("phrase_key")
        source = event.get("source")
        if not isinstance(phrase, str) or not phrase or source not in {"A", "B"}:
            raise Stage2RDynamicSpineAuditError("Stage2G source path identity malformed")
        paths[(phrase, str(source))].append(event)
    if len(paths) != EXPECTED_STAGE2G_MATERIALIZABLE_SOURCE_PATH_COUNT:
        raise Stage2RDynamicSpineAuditError("Stage2G source path count changed")

    archive_file = _bounded_regular_file(archive_path, max_bytes=MAX_ARCHIVE_BYTES, label="archive")
    if _sha256_file(archive_file) != PINNED_TAVERN_ARCHIVE_SHA256:
        raise Stage2RDynamicSpineAuditError("TAVERN archive SHA-256 mismatch")

    score_cache: dict[str, dict[str, object]] = {}
    score_dynamic: set[tuple[str, str]] = set()
    joined_dynamic: set[tuple[str, str]] = set()
    score_op_path_counts: Counter[str] = Counter()
    joined_op_path_counts: Counter[str] = Counter()
    score_op_occurrences: Counter[str] = Counter()
    joined_op_occurrences: Counter[str] = Counter()
    score_initial_hist: Counter[int] = Counter()
    joined_initial_hist: Counter[int] = Counter()
    score_max_hist: Counter[int] = Counter()
    joined_max_hist: Counter[int] = Counter()

    try:
        with zipfile.ZipFile(archive_file) as archive:
            infos = _validated_zip_members(archive)
            corrupt = archive.testzip()
            if corrupt is not None:
                raise Stage2RDynamicSpineAuditError(f"corrupt archive member: {corrupt}")
            root = _archive_root(infos)
            for phrase, source in sorted(paths):
                if phrase not in score_cache:
                    score_info = _score_member(infos, root=root, phrase_key=phrase)
                    if score_info.file_size > MAX_SCORE_BYTES:
                        raise Stage2RDynamicSpineAuditError("score source exceeds size bound")
                    try:
                        score_text = archive.read(score_info).decode("utf-8", errors="strict")
                    except UnicodeDecodeError as exc:
                        raise Stage2RDynamicSpineAuditError("score source is not strict UTF-8") from exc
                    score_cache[phrase] = scan_spine_topology(score_text, source_kind="SCORE")
                score_result = score_cache[phrase]
                joined_info = _joined_member(infos, root=root, phrase_key=phrase, source=source)
                try:
                    joined_text = archive.read(joined_info).decode("utf-8", errors="strict")
                except UnicodeDecodeError as exc:
                    raise Stage2RDynamicSpineAuditError("Joined source is not strict UTF-8") from exc
                joined_result = scan_spine_topology(joined_text, source_kind="JOINED")

                path_key = (phrase, source)
                if score_result["dynamic_path_present"]:
                    score_dynamic.add(path_key)
                if joined_result["dynamic_path_present"]:
                    joined_dynamic.add(path_key)
                for token in OBSERVED_DYNAMIC_TOKENS:
                    score_count = int(dict(score_result["operation_occurrences"])[token])
                    joined_count = int(dict(joined_result["operation_occurrences"])[token])
                    score_op_occurrences[token] += score_count
                    joined_op_occurrences[token] += joined_count
                    if score_count:
                        score_op_path_counts[token] += 1
                    if joined_count:
                        joined_op_path_counts[token] += 1
                score_initial_hist[int(score_result["initial_kern_spine_count"])] += 1
                joined_initial_hist[int(joined_result["initial_kern_spine_count"])] += 1
                score_max_hist[int(score_result["max_observed_kern_spine_count"])] += 1
                joined_max_hist[int(joined_result["max_observed_kern_spine_count"])] += 1
    except zipfile.BadZipFile as exc:
        raise Stage2RDynamicSpineAuditError("invalid TAVERN ZIP archive") from exc

    union = score_dynamic | joined_dynamic
    intersection = score_dynamic & joined_dynamic
    summary = {
        "schema_version": SUMMARY_SCHEMA,
        "source_corpus": SOURCE_CORPUS,
        "eligible_original_partition": "TRAIN",
        "source_stage2g_private_event_manifest_sha256": EXPECTED_STAGE2G_PRIVATE_EVENT_MANIFEST_SHA256,
        "source_tavern_archive_sha256": PINNED_TAVERN_ARCHIVE_SHA256,
        "source_path_count": len(paths),
        "materialized_event_count": len(events),
        "score_dynamic_source_path_count": len(score_dynamic),
        "joined_dynamic_source_path_count": len(joined_dynamic),
        "dynamic_union_source_path_count": len(union),
        "dynamic_intersection_source_path_count": len(intersection),
        "score_only_dynamic_source_path_count": len(score_dynamic - joined_dynamic),
        "joined_only_dynamic_source_path_count": len(joined_dynamic - score_dynamic),
        "score_operation_path_counts": {token: score_op_path_counts[token] for token in OBSERVED_DYNAMIC_TOKENS},
        "joined_operation_path_counts": {token: joined_op_path_counts[token] for token in OBSERVED_DYNAMIC_TOKENS},
        "score_operation_occurrence_counts": {token: score_op_occurrences[token] for token in OBSERVED_DYNAMIC_TOKENS},
        "joined_operation_occurrence_counts": {token: joined_op_occurrences[token] for token in OBSERVED_DYNAMIC_TOKENS},
        "score_initial_kern_spine_count_histogram": {str(key): score_initial_hist[key] for key in sorted(score_initial_hist)},
        "joined_initial_kern_spine_count_histogram": {str(key): joined_initial_hist[key] for key in sorted(joined_initial_hist)},
        "score_max_observed_kern_spine_count_histogram": {str(key): score_max_hist[key] for key in sorted(score_max_hist)},
        "joined_max_observed_kern_spine_count_histogram": {str(key): joined_max_hist[key] for key in sorted(joined_max_hist)},
        "exchange_or_add_observed": bool(
            score_op_occurrences["*x"]
            or score_op_occurrences["*+"]
            or joined_op_occurrences["*x"]
            or joined_op_occurrences["*+"]
        ),
        "split_join_only_dynamic_topology_observed": bool(union)
        and not bool(
            score_op_occurrences["*x"]
            or score_op_occurrences["*+"]
            or joined_op_occurrences["*x"]
            or joined_op_occurrences["*+"]
        ),
        "dynamic_spine_materialization_authorized": False,
        "timing_inference_used": False,
        "function_target_value_access_for_topology": False,
        "joined_harmonic_label_value_access_for_topology": False,
        "model_feature_materialization_authorized": False,
        "model_training_started": False,
        "model_selection_started": False,
        "non_train_access": False,
        "production_authority": False,
        "deterministic_resolver_remains_authoritative": True,
        "decision": "SPLIT_JOIN_TOPOLOGY_BOUNDED_DESIGN_EXACT_LINEAGE_MATERIALIZER_NEXT",
    }
    rendered = json.dumps(summary, sort_keys=True, ensure_ascii=False)
    for forbidden in ("phrase_key", "function_token", "carrier_event_id", "source_annotation_sha256"):
        if f'"{forbidden}"' in rendered:
            raise Stage2RDynamicSpineAuditError("shareable Stage 2-R summary leaks private event data")
    return summary


def run_stage2r_audit_from_files(stage2g_private_path: str | Path, *, archive_path: str | Path) -> dict[str, object]:
    require_locked_runtime()
    stage2g_data = load_bounded_json(stage2g_private_path, max_bytes=MAX_PRIVATE_BYTES)
    return run_stage2r_audit(stage2g_data, archive_path=archive_path)


def canonical_stage2r_json(data: dict[str, object]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
