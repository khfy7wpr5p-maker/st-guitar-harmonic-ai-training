from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import zipfile
from typing import Any

from .offline_experiment import require_locked_runtime
from .safe_ingest import load_bounded_json
from .stage1e_internal_cv import FOLD_COUNT, PINNED_GROUP_PLAN_SHA256
from .stage2f_function_alignment import _is_data_token
from .stage2g_function_onset_events import (
    MAX_ARCHIVE_BYTES,
    MAX_LABEL_BYTES,
    PINNED_TAVERN_ARCHIVE_SHA256,
    _archive_root,
    _bounded_regular_file,
    _selected_member,
    _sha256_file,
    _validated_zip_members,
)
from .stage2h_function_event_cv import (
    EXPECTED_STAGE2G_EVENT_COUNT,
    EXPECTED_STAGE2G_MATERIALIZABLE_SOURCE_PATH_COUNT,
    EXPECTED_STAGE2G_PRIVATE_EVENT_MANIFEST_SHA256,
    MAX_PRIVATE_BYTES,
    _validate_stage2g_private_payload,
)

CONTRACT_SCHEMA = "st-stage2k-local-harmonic-context-feasibility-audit-contract-v1"
SUMMARY_SCHEMA = "st-stage2k-local-harmonic-context-feasibility-audit-summary-v1"
SOURCE_CORPUS = "TAVERN_REVIEWED_694"
CONTEXT_SOURCE = "HUMAN_SELECTED_ENCODER_HARMONIC_SPINE"


class Stage2KLocalHarmonicContextAuditError(ValueError):
    pass


def build_stage2k_contract() -> dict[str, object]:
    return {
        "schema_version": CONTRACT_SCHEMA,
        "source_corpus": SOURCE_CORPUS,
        "eligible_original_partition": "TRAIN",
        "source_stage1e_group_plan_manifest_sha256": PINNED_GROUP_PLAN_SHA256,
        "source_stage2g_private_event_manifest_sha256": EXPECTED_STAGE2G_PRIVATE_EVENT_MANIFEST_SHA256,
        "source_stage2g_materialized_event_count": EXPECTED_STAGE2G_EVENT_COUNT,
        "source_stage2g_materializable_source_path_count": EXPECTED_STAGE2G_MATERIALIZABLE_SOURCE_PATH_COUNT,
        "source_tavern_archive_sha256": PINNED_TAVERN_ARCHIVE_SHA256,
        "audit_scope": "EXISTING_ENCODER_HARMONIC_SPINE_CONTEXT_AROUND_STAGE2G_CARRIERS_ONLY",
        "context_source": CONTEXT_SOURCE,
        "audited_context_positions": ["PREVIOUS_HARMONIC_EVENT", "CURRENT_CARRIER_HARMONIC_EVENT", "NEXT_HARMONIC_EVENT"],
        "feature_materialization_authorized": False,
        "model_training_started": False,
        "model_selection_started": False,
        "full_train_final_fit_started": False,
        "inference_time_feature_availability_established": False,
        "joined_harmonic_labels_authoritative": False,
        "function_token_rewrite_authorized": False,
        "duration_inference_authorized": False,
        "segment_boundary_inference_authorized": False,
        "non_train_annotation_bodies_materialized": False,
        "original_validation_target_access": False,
        "calibration_target_access": False,
        "holdout_target_access": False,
        "production_authority": False,
        "deterministic_resolver_remains_authoritative": True,
    }


def validate_stage2k_contract(data: object) -> dict[str, object]:
    expected = build_stage2k_contract()
    if not isinstance(data, dict) or data != expected:
        raise Stage2KLocalHarmonicContextAuditError("Stage 2-K contract differs from frozen audit contract")
    return data


def _parse_harmonic_tokens(encoder_text: str) -> list[str]:
    lines = encoder_text.splitlines()
    headers = [
        (index, [cell.strip() for cell in line.split("\t")])
        for index, line in enumerate(lines)
        if line.startswith("**")
    ]
    if len(headers) != 1:
        raise Stage2KLocalHarmonicContextAuditError("expected exactly one analysis header")
    header_index, columns = headers[0]
    harmonic_names = [name for name in ("**harm", "**chords") if name in columns]
    if len(harmonic_names) != 1:
        raise Stage2KLocalHarmonicContextAuditError("expected exactly one harmonic carrier spine")
    harmonic_index = columns.index(harmonic_names[0])
    tokens: list[str] = []
    for line in lines[header_index + 1 :]:
        if not line or line.startswith("!!"):
            continue
        cells = line.split("\t")
        if len(cells) != len(columns):
            raise Stage2KLocalHarmonicContextAuditError("row width mismatch")
        token = cells[harmonic_index].strip()
        if _is_data_token(token):
            tokens.append(token)
    if not tokens:
        raise Stage2KLocalHarmonicContextAuditError("harmonic carrier spine has no data events")
    return tokens


def _audit_path_context(events: list[dict[str, Any]], harmonic_tokens: list[str]) -> dict[str, object]:
    if not events:
        raise Stage2KLocalHarmonicContextAuditError("empty Stage 2-G source path")
    current: list[str] = []
    previous: list[str] = []
    following: list[str] = []
    triples: list[tuple[str, str, str]] = []
    one_sided_or_better = 0
    for event in sorted(events, key=lambda item: int(item["function_event_index"])):
        index = event.get("carrier_harmonic_event_index")
        if not isinstance(index, int) or isinstance(index, bool) or index < 0 or index >= len(harmonic_tokens):
            raise Stage2KLocalHarmonicContextAuditError("carrier harmonic event index is out of range")
        token = harmonic_tokens[index]
        current.append(token)
        has_prev = index > 0
        has_next = index + 1 < len(harmonic_tokens)
        if has_prev:
            previous.append(harmonic_tokens[index - 1])
        if has_next:
            following.append(harmonic_tokens[index + 1])
        if has_prev or has_next:
            one_sided_or_better += 1
        if has_prev and has_next:
            triples.append((harmonic_tokens[index - 1], token, harmonic_tokens[index + 1]))
    return {
        "event_count": len(events),
        "current_count": len(current),
        "previous_count": len(previous),
        "next_count": len(following),
        "one_sided_or_better_count": one_sided_or_better,
        "full_triplet_count": len(triples),
        "current_tokens": current,
        "previous_tokens": previous,
        "next_tokens": following,
        "triples": triples,
    }


def run_stage2k_audit(stage2g_data: object, *, archive_path: str | Path) -> dict[str, object]:
    validate_stage2k_contract(build_stage2k_contract())
    events = _validate_stage2g_private_payload(stage2g_data)
    paths: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    fold_events: Counter[int] = Counter()
    for raw in events:
        if not isinstance(raw, dict):
            raise Stage2KLocalHarmonicContextAuditError("Stage 2-G event row malformed")
        phrase = raw.get("phrase_key")
        source = raw.get("source")
        fold = raw.get("development_fold")
        raw_sha = raw.get("source_annotation_sha256")
        if not isinstance(phrase, str) or not phrase or source not in {"A", "B"}:
            raise Stage2KLocalHarmonicContextAuditError("Stage 2-G event identity malformed")
        if not isinstance(fold, int) or isinstance(fold, bool) or fold not in range(FOLD_COUNT):
            raise Stage2KLocalHarmonicContextAuditError("Stage 2-G fold malformed")
        if not isinstance(raw_sha, str) or len(raw_sha) != 64:
            raise Stage2KLocalHarmonicContextAuditError("Stage 2-G annotation digest malformed")
        paths[(phrase, str(source))].append(raw)
        fold_events[fold] += 1
    if len(paths) != EXPECTED_STAGE2G_MATERIALIZABLE_SOURCE_PATH_COUNT:
        raise Stage2KLocalHarmonicContextAuditError("Stage 2-G source path count changed")

    archive_file = _bounded_regular_file(archive_path, max_bytes=MAX_ARCHIVE_BYTES, label="archive")
    if _sha256_file(archive_file) != PINNED_TAVERN_ARCHIVE_SHA256:
        raise Stage2KLocalHarmonicContextAuditError("TAVERN archive SHA-256 mismatch")

    totals: Counter[str] = Counter()
    unique_current: set[str] = set()
    unique_previous: set[str] = set()
    unique_next: set[str] = set()
    unique_triples: set[tuple[str, str, str]] = set()
    harmonic_events_per_path: list[int] = []

    with zipfile.ZipFile(archive_file) as archive:
        infos = _validated_zip_members(archive)
        corrupt = archive.testzip()
        if corrupt is not None:
            raise Stage2KLocalHarmonicContextAuditError(f"corrupt archive member: {corrupt}")
        _archive_root(infos)
        for (phrase, source), path_events in sorted(paths.items()):
            member = _selected_member(infos, phrase, source)
            if member.file_size > MAX_LABEL_BYTES:
                raise Stage2KLocalHarmonicContextAuditError("TRAIN annotation exceeds size bound")
            raw = archive.read(member)
            expected_hashes = {str(item["source_annotation_sha256"]) for item in path_events}
            if len(expected_hashes) != 1 or hashlib.sha256(raw).hexdigest() not in expected_hashes:
                raise Stage2KLocalHarmonicContextAuditError("TRAIN annotation SHA-256 differs from Stage 2-G provenance")
            try:
                text = raw.decode("utf-8", errors="strict")
            except UnicodeDecodeError as exc:
                raise Stage2KLocalHarmonicContextAuditError("TRAIN annotation is not UTF-8") from exc
            harmonic_tokens = _parse_harmonic_tokens(text)
            harmonic_events_per_path.append(len(harmonic_tokens))
            result = _audit_path_context(path_events, harmonic_tokens)
            totals["event_count"] += int(result["event_count"])
            totals["current_count"] += int(result["current_count"])
            totals["previous_count"] += int(result["previous_count"])
            totals["next_count"] += int(result["next_count"])
            totals["one_sided_or_better_count"] += int(result["one_sided_or_better_count"])
            totals["full_triplet_count"] += int(result["full_triplet_count"])
            unique_current.update(result["current_tokens"])
            unique_previous.update(result["previous_tokens"])
            unique_next.update(result["next_tokens"])
            unique_triples.update(result["triples"])

    if totals["event_count"] != EXPECTED_STAGE2G_EVENT_COUNT or totals["current_count"] != EXPECTED_STAGE2G_EVENT_COUNT:
        raise Stage2KLocalHarmonicContextAuditError("carrier context coverage is not complete")

    event_count = EXPECTED_STAGE2G_EVENT_COUNT
    summary = {
        "schema_version": SUMMARY_SCHEMA,
        "source_corpus": SOURCE_CORPUS,
        "eligible_original_partition": "TRAIN",
        "source_stage1e_group_plan_manifest_sha256": PINNED_GROUP_PLAN_SHA256,
        "source_stage2g_private_event_manifest_sha256": EXPECTED_STAGE2G_PRIVATE_EVENT_MANIFEST_SHA256,
        "source_tavern_archive_sha256": PINNED_TAVERN_ARCHIVE_SHA256,
        "context_source": CONTEXT_SOURCE,
        "materialized_event_count": event_count,
        "source_path_count": len(paths),
        "fold_event_distribution": {str(i): fold_events[i] for i in range(FOLD_COUNT)},
        "current_carrier_harmonic_token_coverage": 1.0,
        "previous_harmonic_event_token_coverage": round(totals["previous_count"] / event_count, 12),
        "next_harmonic_event_token_coverage": round(totals["next_count"] / event_count, 12),
        "one_sided_or_better_context_coverage": round(totals["one_sided_or_better_count"] / event_count, 12),
        "full_prev_current_next_context_coverage": round(totals["full_triplet_count"] / event_count, 12),
        "current_carrier_harmonic_token_event_count": totals["current_count"],
        "previous_harmonic_event_token_event_count": totals["previous_count"],
        "next_harmonic_event_token_event_count": totals["next_count"],
        "full_prev_current_next_context_event_count": totals["full_triplet_count"],
        "unique_current_carrier_harmonic_token_count": len(unique_current),
        "unique_previous_harmonic_token_count": len(unique_previous),
        "unique_next_harmonic_token_count": len(unique_next),
        "unique_full_context_triplet_count": len(unique_triples),
        "harmonic_event_count_per_path_min": min(harmonic_events_per_path),
        "harmonic_event_count_per_path_max": max(harmonic_events_per_path),
        "audit_supported_context_candidates": [
            "CURRENT_CARRIER_HARMONIC_TOKEN",
            "PREVIOUS_HARMONIC_EVENT_TOKEN_WHEN_PRESENT",
            "NEXT_HARMONIC_EVENT_TOKEN_WHEN_PRESENT",
        ],
        "inference_time_feature_availability_established": False,
        "feature_materialization_authorized": False,
        "model_training_started": False,
        "model_selection_started": False,
        "full_train_final_fit_started": False,
        "joined_harmonic_labels_authoritative": False,
        "function_token_rewrite_used": False,
        "duration_inference_used": False,
        "segment_boundary_inference_used": False,
        "non_train_annotation_bodies_materialized": False,
        "original_validation_target_access": False,
        "calibration_target_access": False,
        "holdout_target_access": False,
        "production_authority": False,
        "deterministic_resolver_remains_authoritative": True,
    }
    rendered = json.dumps(summary, sort_keys=True, ensure_ascii=False)
    for forbidden in ("phrase_key", "carrier_event_id", "function_token", "source_annotation_sha256"):
        if f'"{forbidden}"' in rendered:
            raise Stage2KLocalHarmonicContextAuditError("shareable Stage 2-K summary leaks private event data")
    return summary


def run_stage2k_audit_from_files(stage2g_private_path: str | Path, archive_path: str | Path) -> dict[str, object]:
    require_locked_runtime()
    data = load_bounded_json(stage2g_private_path, max_bytes=MAX_PRIVATE_BYTES)
    return run_stage2k_audit(data, archive_path=archive_path)


def canonical_stage2k_json(data: dict[str, object]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
