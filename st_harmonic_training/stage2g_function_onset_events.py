from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import stat
import zipfile
from typing import Any

from .offline_experiment import require_locked_runtime
from .safe_ingest import load_bounded_json
from .stage1e_internal_cv import (
    FOLD_COUNT,
    PINNED_GROUP_PLAN_SHA256,
    build_stage1e_group_plan,
)
from .stage2b_specialist_materialization import (
    SOURCE_CORPUS,
    _sha256_file,
    _validate_decision_data,
    build_train_identity_map,
)
from .stage2c_contract import (
    PINNED_STAGE2B_PRIVATE_RECORD_MANIFEST_SHA256,
    PINNED_STAGE2B_SOURCE_TARGET_SLOT_COUNT,
)
from .stage2f_function_alignment import (
    EXPECTED_FUNCTION_ELIGIBLE_RECORD_COUNT,
    EXPECTED_FUNCTION_SUPPORTED_SOURCE_TARGET_COUNT,
    EXPECTED_TRAIN_RECORD_COUNT,
    EXPECTED_TRAIN_WORK_FAMILY_COUNT,
    Stage2FFunctionAlignmentError,
    _is_data_token,
    classify_function_source_path,
)
from .tavern_event_alignment_audit import (
    PINNED_ALIGNMENT_MANIFEST_SHA256,
    _joined_member,
)
from .tavern_gold_materialization import PINNED_VALIDATED_SHA256
from .tavern_raw_label_realization import (
    MAX_ARCHIVE_BYTES,
    MAX_DECISION_BYTES,
    MAX_LABEL_BYTES,
    PINNED_TAVERN_ARCHIVE_SHA256,
    _bounded_regular_file,
    _selected_member,
    _selected_sources,
    _validated_zip_members,
)
from .tavern_reviewed_split import build_tavern_reviewed_split_from_file
from .tavern_score_input_realization import _archive_root
from .tavern_structure import PINNED_TAVERN_REVISION

CONTRACT_SCHEMA = "st-stage2g-function-onset-event-target-contract-v1"
MATERIALIZATION_SCHEMA = "st-stage2g-function-onset-events-private-v1"
SUMMARY_SCHEMA = "st-stage2g-function-onset-events-summary-v1"
PRIVATE_RECEIPT_SCHEMA = "st-stage2f-function-event-carrier-private-receipt-v1"

FUNCTION_SPECIALIST_TARGET_SHAPE = "ONSET_EVENT"
TARGET_AUTHORITY = "HUMAN_SELECTED_ENCODER_FUNCTION_TOKEN"
CARRIER_AUTHORITY = "ENCODER_HARMONIC_EVENT_WITH_JOINED_STRUCTURE_EVIDENCE"
REJECTED_TARGET_SHAPES = (
    "AUTO_FILLED_FUNCTION",
    "EVENT_WITH_INFERRED_DURATION",
    "JOINED_HARMONIC_LABEL_AS_FUNCTION_AUTHORITY",
    "SEGMENT_WITH_INFERRED_DURATION",
    "WHOLE_PHRASE_SEQUENCE_AS_CLASS",
)
PINNED_STAGE2F_DIAGNOSTIC_MANIFEST_SHA256 = (
    "968ea1afb3746d93702561c9472c01f3d6045866eb428447a20b14a22039885b"
)

EXPECTED_ONSET_CANDIDATE_RECORD_COUNT = 355
EXPECTED_QUARANTINE_RECORD_COUNT = 123
EXPECTED_ONSET_CANDIDATE_SOURCE_PATH_COUNT = 366
EXPECTED_MATERIALIZABLE_SOURCE_PATH_COUNT = 363
EXPECTED_QUARANTINE_SOURCE_PATH_COUNT = 125
EXPECTED_FOLD_RECORD_DISTRIBUTION = {"0": 156, "1": 167, "2": 164}
EXPECTED_FOLD_FUNCTION_ELIGIBLE_RECORD_DISTRIBUTION = {
    "0": 156,
    "1": 167,
    "2": 155,
}
EXPECTED_FOLD_CANDIDATE_RECORD_DISTRIBUTION = {"0": 97, "1": 130, "2": 128}
EXPECTED_FOLD_WORK_FAMILY_DISTRIBUTION = {"0": 6, "1": 6, "2": 6}
EXPECTED_STAGE2F_FUNCTION_EVENT_COUNT = 2406
EXPECTED_STAGE2F_FUNCTION_ON_HARMONIC_EVENT_COUNT = 2405
EXPECTED_STAGE2F_FUNCTION_WITHOUT_HARMONIC_EVENT_COUNT = 1
EXPECTED_STAGE2F_FUNCTION_RECIPROCAL_EXPLICIT_COUNT = 865
EXPECTED_STAGE2F_FUNCTION_HARMONIC_RECIPROCAL_COMPARABLE_COUNT = 865
EXPECTED_STAGE2F_FUNCTION_HARMONIC_RECIPROCAL_EXACT_COUNT = 792
EXPECTED_STAGE2F_FUNCTION_HARMONIC_RECIPROCAL_MISMATCH_COUNT = 73
EXPECTED_STAGE2F_DURATION_EXACT_SOURCE_PATH_COUNT = 47

PRIVATE_RECEIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "evidence"
    / "stage2f_function_alignment_private_receipt.v1.json"
)
MAX_PRIVATE_EVENTS = 100_000


class Stage2GFunctionOnsetEventError(ValueError):
    pass


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _expected_private_receipt() -> dict[str, object]:
    return {
        "schema_version": PRIVATE_RECEIPT_SCHEMA,
        "source_corpus": SOURCE_CORPUS,
        "source_revision": PINNED_TAVERN_REVISION,
        "validated_human_decisions_sha256": PINNED_VALIDATED_SHA256,
        "archive_sha256": PINNED_TAVERN_ARCHIVE_SHA256,
        "source_stage1e_group_plan_manifest_sha256": PINNED_GROUP_PLAN_SHA256,
        "source_stage2b_private_record_manifest_sha256": (
            PINNED_STAGE2B_PRIVATE_RECORD_MANIFEST_SHA256
        ),
        "input_record_count": EXPECTED_TRAIN_RECORD_COUNT,
        "function_eligible_record_count": EXPECTED_FUNCTION_ELIGIBLE_RECORD_COUNT,
        "onset_carrier_candidate_record_count": EXPECTED_ONSET_CANDIDATE_RECORD_COUNT,
        "quarantine_record_count": EXPECTED_QUARANTINE_RECORD_COUNT,
        "selected_source_path_count": PINNED_STAGE2B_SOURCE_TARGET_SLOT_COUNT,
        "function_supported_source_target_count": (
            EXPECTED_FUNCTION_SUPPORTED_SOURCE_TARGET_COUNT
        ),
        "onset_carrier_candidate_source_path_count": (
            EXPECTED_ONSET_CANDIDATE_SOURCE_PATH_COUNT
        ),
        "quarantine_source_path_count": EXPECTED_QUARANTINE_SOURCE_PATH_COUNT,
        "duration_exact_source_path_count": EXPECTED_STAGE2F_DURATION_EXACT_SOURCE_PATH_COUNT,
        "function_event_count": EXPECTED_STAGE2F_FUNCTION_EVENT_COUNT,
        "function_on_harmonic_event_count": (
            EXPECTED_STAGE2F_FUNCTION_ON_HARMONIC_EVENT_COUNT
        ),
        "function_without_harmonic_event_count": (
            EXPECTED_STAGE2F_FUNCTION_WITHOUT_HARMONIC_EVENT_COUNT
        ),
        "function_reciprocal_explicit_count": (
            EXPECTED_STAGE2F_FUNCTION_RECIPROCAL_EXPLICIT_COUNT
        ),
        "function_harmonic_reciprocal_comparable_count": (
            EXPECTED_STAGE2F_FUNCTION_HARMONIC_RECIPROCAL_COMPARABLE_COUNT
        ),
        "function_harmonic_reciprocal_exact_count": (
            EXPECTED_STAGE2F_FUNCTION_HARMONIC_RECIPROCAL_EXACT_COUNT
        ),
        "function_harmonic_reciprocal_mismatch_count": (
            EXPECTED_STAGE2F_FUNCTION_HARMONIC_RECIPROCAL_MISMATCH_COUNT
        ),
        "fold_record_distribution": EXPECTED_FOLD_RECORD_DISTRIBUTION,
        "fold_function_eligible_record_distribution": (
            EXPECTED_FOLD_FUNCTION_ELIGIBLE_RECORD_DISTRIBUTION
        ),
        "fold_onset_carrier_candidate_record_distribution": (
            EXPECTED_FOLD_CANDIDATE_RECORD_DISTRIBUTION
        ),
        "fold_work_family_distribution": EXPECTED_FOLD_WORK_FAMILY_DISTRIBUTION,
        "diagnostic_manifest_sha256": PINNED_STAGE2F_DIAGNOSTIC_MANIFEST_SHA256,
        "target_values_serialized": False,
        "non_train_annotation_bodies_materialized": False,
        "original_validation_target_access": False,
        "calibration_target_access": False,
        "holdout_target_access": False,
        "stage1d_quarantine_reuse_authorized": False,
        "model_fitting_started": False,
        "model_selection_started": False,
        "event_level_training_authorized": False,
        "production_authority": False,
    }


def load_and_validate_stage2f_private_receipt(
    path: str | Path = PRIVATE_RECEIPT_PATH,
) -> dict[str, object]:
    receipt = load_bounded_json(path, max_bytes=64 * 1024)
    expected = _expected_private_receipt()
    if not isinstance(receipt, dict) or receipt != expected:
        raise Stage2GFunctionOnsetEventError(
            "Stage 2-F private receipt differs from frozen bounded evidence"
        )
    return receipt


def _assert_target_partition(partition: str) -> None:
    if partition != "TRAIN":
        raise Stage2GFunctionOnsetEventError(
            f"Stage 2-G annotation access is TRAIN-only: {partition}"
        )


def build_stage2g_contract() -> dict[str, object]:
    receipt = load_and_validate_stage2f_private_receipt()
    plan = build_stage1e_group_plan()
    if plan.get("group_plan_manifest_sha256") != PINNED_GROUP_PLAN_SHA256:
        raise Stage2GFunctionOnsetEventError("Stage 1-E group plan digest changed")
    _assert_target_partition("TRAIN")
    return {
        "schema_version": CONTRACT_SCHEMA,
        "source_corpus": SOURCE_CORPUS,
        "source_revision": PINNED_TAVERN_REVISION,
        "validated_human_decisions_sha256": PINNED_VALIDATED_SHA256,
        "archive_sha256": PINNED_TAVERN_ARCHIVE_SHA256,
        "source_stage1d_alignment_manifest_sha256": PINNED_ALIGNMENT_MANIFEST_SHA256,
        "source_stage1e_group_plan_manifest_sha256": PINNED_GROUP_PLAN_SHA256,
        "source_stage2b_private_record_manifest_sha256": (
            PINNED_STAGE2B_PRIVATE_RECORD_MANIFEST_SHA256
        ),
        "source_stage2f_diagnostic_manifest_sha256": (
            PINNED_STAGE2F_DIAGNOSTIC_MANIFEST_SHA256
        ),
        "eligible_original_partition": "TRAIN",
        "input_record_count": EXPECTED_TRAIN_RECORD_COUNT,
        "function_eligible_record_count": EXPECTED_FUNCTION_ELIGIBLE_RECORD_COUNT,
        "onset_carrier_candidate_record_count": EXPECTED_ONSET_CANDIDATE_RECORD_COUNT,
        "quarantine_record_count": EXPECTED_QUARANTINE_RECORD_COUNT,
        "selected_source_path_count": PINNED_STAGE2B_SOURCE_TARGET_SLOT_COUNT,
        "function_supported_source_target_count": (
            EXPECTED_FUNCTION_SUPPORTED_SOURCE_TARGET_COUNT
        ),
        "onset_carrier_candidate_source_path_count": (
            EXPECTED_ONSET_CANDIDATE_SOURCE_PATH_COUNT
        ),
        "quarantine_source_path_count": EXPECTED_QUARANTINE_SOURCE_PATH_COUNT,
        "materializable_source_path_count": EXPECTED_MATERIALIZABLE_SOURCE_PATH_COUNT,
        "fold_count": FOLD_COUNT,
        "work_family_count": EXPECTED_TRAIN_WORK_FAMILY_COUNT,
        "fold_record_distribution": receipt["fold_record_distribution"],
        "fold_function_eligible_record_distribution": (
            receipt["fold_function_eligible_record_distribution"]
        ),
        "fold_onset_carrier_candidate_record_distribution": (
            receipt["fold_onset_carrier_candidate_record_distribution"]
        ),
        "fold_work_family_distribution": receipt["fold_work_family_distribution"],
        "function_specialist_target_shape": FUNCTION_SPECIALIST_TARGET_SHAPE,
        "target_authority": TARGET_AUTHORITY,
        "carrier_authority": CARRIER_AUTHORITY,
        "rejected_target_shapes": list(REJECTED_TARGET_SHAPES),
        "private_payload_external_only": True,
        "event_target_materialization_authorized": True,
        "joined_harmonic_labels_authoritative": False,
        "duration_inference_authorized": False,
        "segment_boundary_inference_authorized": False,
        "function_token_rewrite_authorized": False,
        "non_train_annotation_bodies_materialized": False,
        "original_validation_target_access": False,
        "calibration_target_access": False,
        "holdout_target_access": False,
        "stage1d_quarantine_reuse_authorized": False,
        "stage2f_quarantine_reuse_authorized": False,
        "model_training_started": False,
        "model_selection_started": False,
        "full_train_final_fit_started": False,
        "event_level_training_authorized": False,
        "production_authority": False,
        "deterministic_resolver_remains_authoritative": True,
    }


def validate_stage2g_contract(data: object) -> dict[str, object]:
    expected = build_stage2g_contract()
    if not isinstance(data, dict) or data != expected:
        raise Stage2GFunctionOnsetEventError(
            "Stage 2-G contract differs from frozen onset-event contract"
        )
    return data


def _parse_onset_event_targets(
    encoder_text: str,
    *,
    phrase_key: str,
    source: str,
    raw_sha256: str,
    split_group_id: str,
    development_fold: int,
) -> list[dict[str, object]]:
    _assert_target_partition("TRAIN")
    if source not in {"A", "B"}:
        raise Stage2GFunctionOnsetEventError("invalid A/B source provenance")
    lines = encoder_text.splitlines()
    headers = [
        (index, [cell.strip() for cell in line.split("\t")])
        for index, line in enumerate(lines)
        if line.startswith("**")
    ]
    if len(headers) != 1:
        raise Stage2GFunctionOnsetEventError(
            f"expected exactly one analysis header: {phrase_key}/{source}"
        )
    header_index, columns = headers[0]
    harmonic_names = [name for name in ("**harm", "**chords") if name in columns]
    if len(harmonic_names) != 1:
        raise Stage2GFunctionOnsetEventError(
            f"expected exactly one harmonic carrier spine: {phrase_key}/{source}"
        )
    function_indices = [index for index, name in enumerate(columns) if name == "**function"]
    if len(function_indices) != 1:
        raise Stage2GFunctionOnsetEventError(
            f"Function target spine must be singular: {phrase_key}/{source}"
        )
    harmonic_index = columns.index(harmonic_names[0])
    function_index = function_indices[0]

    harmonic_event_index = -1
    function_event_index = 0
    rows: list[dict[str, object]] = []
    seen_event_ids: set[str] = set()
    for source_order_index, line in enumerate(
        lines[header_index + 1 :], start=header_index + 1
    ):
        if not line or line.startswith("!!"):
            continue
        cells = line.split("\t")
        if len(cells) != len(columns):
            raise Stage2GFunctionOnsetEventError(
                f"row width mismatch: {phrase_key}/{source}"
            )
        harmonic_token = cells[harmonic_index].strip()
        function_token = cells[function_index].strip()
        harmonic_is_data = _is_data_token(harmonic_token)
        if harmonic_is_data:
            harmonic_event_index += 1
        if not _is_data_token(function_token):
            continue
        if not harmonic_is_data:
            raise Stage2GFunctionOnsetEventError(
                f"Function target lacks harmonic onset carrier: {phrase_key}/{source}"
            )

        identity_seed = {
            "phrase_key": phrase_key,
            "source": source,
            "source_annotation_sha256": raw_sha256,
            "carrier_harmonic_event_index": harmonic_event_index,
            "function_event_index": function_event_index,
        }
        carrier_event_id = _canonical_sha256(identity_seed)
        if carrier_event_id in seen_event_ids:
            raise Stage2GFunctionOnsetEventError(
                f"duplicate event identity: {phrase_key}/{source}"
            )
        seen_event_ids.add(carrier_event_id)
        rows.append(
            {
                "phrase_key": phrase_key,
                "source": source,
                "source_annotation_sha256": raw_sha256,
                "split_group_id": split_group_id,
                "development_fold": development_fold,
                "carrier_event_id": carrier_event_id,
                "carrier_harmonic_event_index": harmonic_event_index,
                "carrier_source_order_index": source_order_index,
                "function_event_index": function_event_index,
                "function_token": function_token,
                "target_shape": FUNCTION_SPECIALIST_TARGET_SHAPE,
            }
        )
        function_event_index += 1

    if not rows:
        raise Stage2GFunctionOnsetEventError(
            f"candidate source has no Function target events: {phrase_key}/{source}"
        )
    return rows


def _validate_fold_safety(train_identity: dict[str, dict[str, object]]) -> None:
    plan = build_stage1e_group_plan()
    if plan.get("group_plan_manifest_sha256") != PINNED_GROUP_PLAN_SHA256:
        raise Stage2GFunctionOnsetEventError("Stage 1-E group plan digest changed")
    planned = {
        str(item["split_group_id"]): int(item["development_fold"])
        for item in plan["groups"]
    }
    observed: dict[str, int] = {}
    for phrase, identity in train_identity.items():
        group = str(identity["split_group_id"])
        fold = int(identity["development_fold"])
        if planned.get(group) != fold:
            raise Stage2GFunctionOnsetEventError(
                f"development fold changed: {phrase}"
            )
        previous = observed.setdefault(group, fold)
        if previous != fold:
            raise Stage2GFunctionOnsetEventError(
                f"work-family leakage across development folds: {group}"
            )


def _claim_unique_source_path(
    seen: set[tuple[str, str]], phrase_key: str, source: str
) -> None:
    key = (phrase_key, source)
    if key in seen:
        raise Stage2GFunctionOnsetEventError(
            f"duplicate selected source path: {phrase_key}/{source}"
        )
    seen.add(key)


def _append_unique_events(
    destination: list[dict[str, object]],
    seen_ids: set[str],
    source_events: list[dict[str, object]],
) -> None:
    for event in source_events:
        event_id = event.get("carrier_event_id")
        if not isinstance(event_id, str) or not event_id or event_id in seen_ids:
            raise Stage2GFunctionOnsetEventError("duplicate/invalid event identity")
        seen_ids.add(event_id)
        destination.append(event)


def _materialize_candidate_record_events(
    source_rows: list[dict[str, object]],
    *,
    phrase_key: str,
    split_group_id: str,
    development_fold: int,
) -> list[dict[str, object]]:
    if not source_rows or any(
        row.get("status") != "FUNCTION_ONSET_CARRIER_CANDIDATE"
        for row in source_rows
    ):
        raise Stage2GFunctionOnsetEventError(
            f"non-candidate/quarantine record cannot materialize: {phrase_key}"
        )
    result: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for row in source_rows:
        source = row.get("source")
        raw_sha256 = row.get("raw_sha256")
        encoder_text = row.get("encoder_text")
        if (
            source not in {"A", "B"}
            or not isinstance(raw_sha256, str)
            or not isinstance(encoder_text, str)
        ):
            raise Stage2GFunctionOnsetEventError("candidate source evidence malformed")
        events = _parse_onset_event_targets(
            encoder_text,
            phrase_key=phrase_key,
            source=str(source),
            raw_sha256=raw_sha256,
            split_group_id=split_group_id,
            development_fold=development_fold,
        )
        _append_unique_events(result, seen_ids, events)
    return result


def _variant_provenance_counts(
    decisions_by_phrase: dict[str, dict[str, Any]],
    materialized_sources_by_phrase: dict[str, set[str]],
    *,
    eligible_phrases: set[str],
) -> dict[str, int]:
    preserve_train_records = 0
    preserve_materialized_records = 0
    preserve_materialized_source_paths = 0
    for phrase in sorted(eligible_phrases):
        decision = decisions_by_phrase[phrase]
        if decision.get("decision") != "PRESERVE_VARIANTS":
            continue
        preserve_train_records += 1
        sources = materialized_sources_by_phrase.get(phrase, set())
        if sources:
            preserve_materialized_records += 1
            preserve_materialized_source_paths += len(sources)
    return {
        "preserve_variants_train_record_count": preserve_train_records,
        "preserve_variants_materialized_record_count": preserve_materialized_records,
        "preserve_variants_materialized_source_path_count": (
            preserve_materialized_source_paths
        ),
    }


def build_stage2g_function_onset_event_materialization(
    decision_data: object,
    *,
    decision_artifact_sha256: str,
    archive_path: str | Path,
    reviewed_split: object,
) -> dict[str, object]:
    validate_stage2g_contract(build_stage2g_contract())
    decisions = _validate_decision_data(
        decision_data,
        artifact_sha256=decision_artifact_sha256,
    )
    decisions_by_phrase = {str(item["phrase_key"]): item for item in decisions}
    train_identity = build_train_identity_map(reviewed_split)
    _validate_fold_safety(train_identity)
    if not set(train_identity).issubset(decisions_by_phrase):
        raise Stage2GFunctionOnsetEventError(
            "TRAIN identity set is not covered by validated decisions"
        )

    archive_file = _bounded_regular_file(
        archive_path, max_bytes=MAX_ARCHIVE_BYTES, label="archive"
    )
    archive_sha256 = _sha256_file(archive_file)
    if archive_sha256 != PINNED_TAVERN_ARCHIVE_SHA256:
        raise Stage2GFunctionOnsetEventError("TAVERN archive SHA-256 mismatch")

    stats: Counter[str] = Counter()
    fold_records: Counter[int] = Counter()
    fold_eligible: Counter[int] = Counter()
    fold_candidates: Counter[int] = Counter()
    fold_groups: dict[int, set[str]] = defaultdict(set)
    diagnostic_manifest_rows: list[dict[str, object]] = []
    materialized_events: list[dict[str, object]] = []
    materialized_sources_by_phrase: dict[str, set[str]] = defaultdict(set)
    source_event_counts: Counter[str] = Counter()
    parsed_annotation_phrases: set[str] = set()
    seen_source_paths: set[tuple[str, str]] = set()
    seen_event_ids: set[str] = set()

    try:
        with zipfile.ZipFile(archive_file) as archive:
            infos = _validated_zip_members(archive)
            corrupt = archive.testzip()
            if corrupt is not None:
                raise Stage2GFunctionOnsetEventError(
                    f"corrupt archive member: {corrupt}"
                )
            root = _archive_root(infos)

            for phrase in sorted(train_identity):
                identity = train_identity[phrase]
                decision = decisions_by_phrase[phrase]
                fold = int(identity["development_fold"])
                group = str(identity["split_group_id"])
                fold_records[fold] += 1
                fold_groups[fold].add(group)
                path_rows: list[dict[str, object]] = []

                for source, expected_hash in _selected_sources(decision):
                    _claim_unique_source_path(seen_source_paths, phrase, source)
                    encoder_info = _selected_member(infos, phrase, source)
                    if encoder_info.file_size > MAX_LABEL_BYTES:
                        raise Stage2GFunctionOnsetEventError(
                            f"TRAIN annotation exceeds size bound: {phrase}/{source}"
                        )
                    encoder_raw = archive.read(encoder_info)
                    actual_hash = hashlib.sha256(encoder_raw).hexdigest()
                    if actual_hash != expected_hash:
                        raise Stage2GFunctionOnsetEventError(
                            f"TRAIN annotation SHA-256 mismatch: {phrase}/{source}"
                        )
                    joined_info = _joined_member(
                        infos,
                        root=root,
                        phrase_key=phrase,
                        source=source,
                    )
                    joined_raw = archive.read(joined_info)
                    try:
                        encoder_text = encoder_raw.decode("utf-8", errors="strict")
                        joined_text = joined_raw.decode("utf-8", errors="strict")
                    except UnicodeDecodeError as exc:
                        raise Stage2GFunctionOnsetEventError(
                            f"TRAIN alignment source is not UTF-8: {phrase}/{source}"
                        ) from exc

                    diagnostic = classify_function_source_path(
                        encoder_text, joined_text
                    )
                    status = str(diagnostic["status"])
                    stats["selected_source_path_count"] += 1
                    stats["onset_carrier_candidate_source_path_count"] += int(
                        status == "FUNCTION_ONSET_CARRIER_CANDIDATE"
                    )
                    stats["quarantine_source_path_count"] += int(
                        status == "QUARANTINE"
                    )
                    stats["missing_function_source_path_count"] += int(
                        status
                        in {"FUNCTION_SPINE_MISSING", "FUNCTION_EVENTS_MISSING"}
                    )
                    diagnostic_manifest_rows.append(
                        {
                            "phrase_key": phrase,
                            "source": source,
                            "development_fold": fold,
                            "status": diagnostic["status"],
                            "function_event_count": diagnostic[
                                "function_event_count"
                            ],
                            "function_on_harmonic_event_count": diagnostic[
                                "function_on_harmonic_event_count"
                            ],
                            "encoder_joined_reciprocal_sequence_exact": diagnostic[
                                "encoder_joined_reciprocal_sequence_exact"
                            ],
                            "duration_exact_single_event_candidate": diagnostic[
                                "duration_exact_single_event_candidate"
                            ],
                            "quarantine_reasons": diagnostic["quarantine_reasons"],
                        }
                    )
                    path_rows.append(
                        {
                            "source": source,
                            "raw_sha256": actual_hash,
                            "encoder_text": encoder_text,
                            "status": status,
                            "function_event_count": int(
                                diagnostic["function_event_count"]
                            ),
                        }
                    )

                parsed_annotation_phrases.add(phrase)
                has_function = all(
                    int(row["function_event_count"]) > 0 for row in path_rows
                )
                if not has_function:
                    stats["missing_function_record_count"] += 1
                    continue

                stats["function_eligible_record_count"] += 1
                fold_eligible[fold] += 1
                is_candidate = all(
                    row["status"] == "FUNCTION_ONSET_CARRIER_CANDIDATE"
                    for row in path_rows
                )
                if not is_candidate:
                    stats["quarantine_record_count"] += 1
                    continue

                stats["onset_carrier_candidate_record_count"] += 1
                fold_candidates[fold] += 1
                record_events = _materialize_candidate_record_events(
                    path_rows,
                    phrase_key=phrase,
                    split_group_id=group,
                    development_fold=fold,
                )
                _append_unique_events(
                    materialized_events, seen_event_ids, record_events
                )
                for row in path_rows:
                    source = str(row["source"])
                    materialized_sources_by_phrase[phrase].add(source)
                for event in record_events:
                    source_event_counts[str(event["source"])] += 1
    except (zipfile.BadZipFile, Stage2FFunctionAlignmentError) as exc:
        raise Stage2GFunctionOnsetEventError(
            "Stage 2-G source materialization failed"
        ) from exc

    if parsed_annotation_phrases != set(train_identity):
        raise Stage2GFunctionOnsetEventError(
            "annotation parse scope differs from TRAIN identity set"
        )

    supported_source_targets = (
        stats["selected_source_path_count"]
        - stats["missing_function_source_path_count"]
    )
    expected_pairs = {
        "selected source path count": (
            stats["selected_source_path_count"],
            PINNED_STAGE2B_SOURCE_TARGET_SLOT_COUNT,
        ),
        "Function supported source target count": (
            supported_source_targets,
            EXPECTED_FUNCTION_SUPPORTED_SOURCE_TARGET_COUNT,
        ),
        "Function eligible record count": (
            stats["function_eligible_record_count"],
            EXPECTED_FUNCTION_ELIGIBLE_RECORD_COUNT,
        ),
        "onset-carrier candidate record count": (
            stats["onset_carrier_candidate_record_count"],
            EXPECTED_ONSET_CANDIDATE_RECORD_COUNT,
        ),
        "quarantine record count": (
            stats["quarantine_record_count"],
            EXPECTED_QUARANTINE_RECORD_COUNT,
        ),
        "onset-carrier candidate source path count": (
            stats["onset_carrier_candidate_source_path_count"],
            EXPECTED_ONSET_CANDIDATE_SOURCE_PATH_COUNT,
        ),
        "quarantine source path count": (
            stats["quarantine_source_path_count"],
            EXPECTED_QUARANTINE_SOURCE_PATH_COUNT,
        ),
    }
    for label, (observed, expected) in expected_pairs.items():
        if observed != expected:
            raise Stage2GFunctionOnsetEventError(
                f"Stage 2-G {label} changed: {observed} != {expected}"
            )

    fold_record_distribution = {
        str(index): fold_records[index] for index in range(FOLD_COUNT)
    }
    fold_eligible_distribution = {
        str(index): fold_eligible[index] for index in range(FOLD_COUNT)
    }
    fold_candidate_distribution = {
        str(index): fold_candidates[index] for index in range(FOLD_COUNT)
    }
    fold_work_family_distribution = {
        str(index): len(fold_groups[index]) for index in range(FOLD_COUNT)
    }
    if fold_record_distribution != EXPECTED_FOLD_RECORD_DISTRIBUTION:
        raise Stage2GFunctionOnsetEventError("fold record distribution changed")
    if (
        fold_eligible_distribution
        != EXPECTED_FOLD_FUNCTION_ELIGIBLE_RECORD_DISTRIBUTION
    ):
        raise Stage2GFunctionOnsetEventError(
            "fold Function-eligible record distribution changed"
        )
    if fold_candidate_distribution != EXPECTED_FOLD_CANDIDATE_RECORD_DISTRIBUTION:
        raise Stage2GFunctionOnsetEventError(
            "fold onset-carrier candidate distribution changed"
        )
    if fold_work_family_distribution != EXPECTED_FOLD_WORK_FAMILY_DISTRIBUTION:
        raise Stage2GFunctionOnsetEventError(
            "fold work-family distribution changed"
        )

    diagnostic_manifest_rows.sort(
        key=lambda item: (str(item["phrase_key"]), str(item["source"]))
    )
    replay_digest = _canonical_sha256(diagnostic_manifest_rows)
    if replay_digest != PINNED_STAGE2F_DIAGNOSTIC_MANIFEST_SHA256:
        raise Stage2GFunctionOnsetEventError(
            "Stage 2-F diagnostic manifest replay changed"
        )

    materialized_source_path_count = sum(
        len(sources) for sources in materialized_sources_by_phrase.values()
    )
    if materialized_source_path_count != EXPECTED_MATERIALIZABLE_SOURCE_PATH_COUNT:
        raise Stage2GFunctionOnsetEventError(
            f"materializable source path count changed: "
            f"{materialized_source_path_count} != "
            f"{EXPECTED_MATERIALIZABLE_SOURCE_PATH_COUNT}"
        )
    materialized_events.sort(
        key=lambda item: (
            str(item["phrase_key"]),
            str(item["source"]),
            int(item["carrier_harmonic_event_index"]),
            int(item["function_event_index"]),
        )
    )
    if not materialized_events or len(materialized_events) > MAX_PRIVATE_EVENTS:
        raise Stage2GFunctionOnsetEventError(
            "private Function onset-event count outside bounds"
        )

    return {
        "schema_version": MATERIALIZATION_SCHEMA,
        "source_corpus": SOURCE_CORPUS,
        "source_revision": PINNED_TAVERN_REVISION,
        "validated_human_decisions_sha256": decision_artifact_sha256,
        "archive_sha256": archive_sha256,
        "source_stage1e_group_plan_manifest_sha256": PINNED_GROUP_PLAN_SHA256,
        "source_stage2b_private_record_manifest_sha256": (
            PINNED_STAGE2B_PRIVATE_RECORD_MANIFEST_SHA256
        ),
        "source_stage2f_diagnostic_manifest_sha256": replay_digest,
        "eligible_original_partition": "TRAIN",
        "input_record_count": EXPECTED_TRAIN_RECORD_COUNT,
        "function_eligible_record_count": stats["function_eligible_record_count"],
        "onset_carrier_candidate_record_count": stats[
            "onset_carrier_candidate_record_count"
        ],
        "quarantine_record_count": stats["quarantine_record_count"],
        "selected_source_path_count": stats["selected_source_path_count"],
        "function_supported_source_target_count": supported_source_targets,
        "onset_carrier_candidate_source_path_count": stats[
            "onset_carrier_candidate_source_path_count"
        ],
        "quarantine_source_path_count": stats["quarantine_source_path_count"],
        "materialized_source_path_count": materialized_source_path_count,
        "fold_record_distribution": fold_record_distribution,
        "fold_function_eligible_record_distribution": fold_eligible_distribution,
        "fold_onset_carrier_candidate_record_distribution": (
            fold_candidate_distribution
        ),
        "fold_work_family_distribution": fold_work_family_distribution,
        "materialized_event_count": len(materialized_events),
        "source_event_counts": {
            "A": source_event_counts["A"],
            "B": source_event_counts["B"],
        },
        "variant_provenance_counts": _variant_provenance_counts(
            decisions_by_phrase,
            materialized_sources_by_phrase,
            eligible_phrases=set(train_identity),
        ),
        "private_event_manifest_sha256": _canonical_sha256(materialized_events),
        "function_specialist_target_shape": FUNCTION_SPECIALIST_TARGET_SHAPE,
        "target_authority": TARGET_AUTHORITY,
        "carrier_authority": CARRIER_AUTHORITY,
        "events": materialized_events,
        "private_payload_external_only": True,
        "non_train_annotation_bodies_materialized": False,
        "original_validation_target_access": False,
        "calibration_target_access": False,
        "holdout_target_access": False,
        "stage1d_quarantine_reuse_authorized": False,
        "stage2f_quarantine_reuse_authorized": False,
        "duration_inference_used": False,
        "segment_boundary_inference_used": False,
        "joined_harmonic_labels_authoritative": False,
        "model_training_started": False,
        "model_selection_started": False,
        "full_train_final_fit_started": False,
        "event_level_training_authorized": False,
        "production_authority": False,
        "deterministic_resolver_remains_authoritative": True,
    }


def build_stage2g_summary(data: object) -> dict[str, object]:
    if not isinstance(data, dict) or data.get("schema_version") != MATERIALIZATION_SCHEMA:
        raise Stage2GFunctionOnsetEventError(
            "unsupported Stage 2-G materialization schema"
        )
    expected = {
        "source_corpus": SOURCE_CORPUS,
        "source_revision": PINNED_TAVERN_REVISION,
        "validated_human_decisions_sha256": PINNED_VALIDATED_SHA256,
        "archive_sha256": PINNED_TAVERN_ARCHIVE_SHA256,
        "source_stage1e_group_plan_manifest_sha256": PINNED_GROUP_PLAN_SHA256,
        "source_stage2b_private_record_manifest_sha256": (
            PINNED_STAGE2B_PRIVATE_RECORD_MANIFEST_SHA256
        ),
        "source_stage2f_diagnostic_manifest_sha256": (
            PINNED_STAGE2F_DIAGNOSTIC_MANIFEST_SHA256
        ),
        "eligible_original_partition": "TRAIN",
        "input_record_count": EXPECTED_TRAIN_RECORD_COUNT,
        "function_eligible_record_count": EXPECTED_FUNCTION_ELIGIBLE_RECORD_COUNT,
        "onset_carrier_candidate_record_count": EXPECTED_ONSET_CANDIDATE_RECORD_COUNT,
        "quarantine_record_count": EXPECTED_QUARANTINE_RECORD_COUNT,
        "selected_source_path_count": PINNED_STAGE2B_SOURCE_TARGET_SLOT_COUNT,
        "function_supported_source_target_count": (
            EXPECTED_FUNCTION_SUPPORTED_SOURCE_TARGET_COUNT
        ),
        "onset_carrier_candidate_source_path_count": (
            EXPECTED_ONSET_CANDIDATE_SOURCE_PATH_COUNT
        ),
        "quarantine_source_path_count": EXPECTED_QUARANTINE_SOURCE_PATH_COUNT,
        "materialized_source_path_count": EXPECTED_MATERIALIZABLE_SOURCE_PATH_COUNT,
        "fold_record_distribution": EXPECTED_FOLD_RECORD_DISTRIBUTION,
        "fold_function_eligible_record_distribution": (
            EXPECTED_FOLD_FUNCTION_ELIGIBLE_RECORD_DISTRIBUTION
        ),
        "fold_onset_carrier_candidate_record_distribution": (
            EXPECTED_FOLD_CANDIDATE_RECORD_DISTRIBUTION
        ),
        "fold_work_family_distribution": EXPECTED_FOLD_WORK_FAMILY_DISTRIBUTION,
        "function_specialist_target_shape": FUNCTION_SPECIALIST_TARGET_SHAPE,
        "target_authority": TARGET_AUTHORITY,
        "carrier_authority": CARRIER_AUTHORITY,
        "private_payload_external_only": True,
        "non_train_annotation_bodies_materialized": False,
        "original_validation_target_access": False,
        "calibration_target_access": False,
        "holdout_target_access": False,
        "stage1d_quarantine_reuse_authorized": False,
        "stage2f_quarantine_reuse_authorized": False,
        "duration_inference_used": False,
        "segment_boundary_inference_used": False,
        "joined_harmonic_labels_authoritative": False,
        "model_training_started": False,
        "model_selection_started": False,
        "full_train_final_fit_started": False,
        "event_level_training_authorized": False,
        "production_authority": False,
        "deterministic_resolver_remains_authoritative": True,
    }
    for field, value in expected.items():
        if data.get(field) != value:
            raise Stage2GFunctionOnsetEventError(
                f"Stage 2-G summary boundary changed: {field}"
            )

    events = data.get("events")
    if not isinstance(events, list) or not all(
        isinstance(item, dict) for item in events
    ):
        raise Stage2GFunctionOnsetEventError("private event rows malformed")
    if data.get("materialized_event_count") != len(events):
        raise Stage2GFunctionOnsetEventError("private event count mismatch")
    if data.get("private_event_manifest_sha256") != _canonical_sha256(events):
        raise Stage2GFunctionOnsetEventError("private event manifest mismatch")

    source_event_counts = data.get("source_event_counts")
    if not isinstance(source_event_counts, dict) or set(source_event_counts) != {"A", "B"}:
        raise Stage2GFunctionOnsetEventError("source A/B event counts malformed")
    if any(
        not isinstance(value, int) or value < 0 for value in source_event_counts.values()
    ):
        raise Stage2GFunctionOnsetEventError("source event count invalid")
    if sum(source_event_counts.values()) != len(events):
        raise Stage2GFunctionOnsetEventError("source event count total mismatch")

    variants = data.get("variant_provenance_counts")
    expected_variant_keys = {
        "preserve_variants_train_record_count",
        "preserve_variants_materialized_record_count",
        "preserve_variants_materialized_source_path_count",
    }
    if not isinstance(variants, dict) or set(variants) != expected_variant_keys:
        raise Stage2GFunctionOnsetEventError("variant provenance counts malformed")
    if any(not isinstance(value, int) or value < 0 for value in variants.values()):
        raise Stage2GFunctionOnsetEventError("variant provenance count invalid")

    fields = (
        "source_corpus",
        "source_revision",
        "validated_human_decisions_sha256",
        "archive_sha256",
        "source_stage1e_group_plan_manifest_sha256",
        "source_stage2b_private_record_manifest_sha256",
        "source_stage2f_diagnostic_manifest_sha256",
        "eligible_original_partition",
        "input_record_count",
        "function_eligible_record_count",
        "onset_carrier_candidate_record_count",
        "quarantine_record_count",
        "selected_source_path_count",
        "function_supported_source_target_count",
        "onset_carrier_candidate_source_path_count",
        "quarantine_source_path_count",
        "materialized_source_path_count",
        "fold_record_distribution",
        "fold_function_eligible_record_distribution",
        "fold_onset_carrier_candidate_record_distribution",
        "fold_work_family_distribution",
        "materialized_event_count",
        "source_event_counts",
        "variant_provenance_counts",
        "private_event_manifest_sha256",
        "function_specialist_target_shape",
        "target_authority",
        "carrier_authority",
        "private_payload_external_only",
        "non_train_annotation_bodies_materialized",
        "original_validation_target_access",
        "calibration_target_access",
        "holdout_target_access",
        "stage1d_quarantine_reuse_authorized",
        "stage2f_quarantine_reuse_authorized",
        "duration_inference_used",
        "segment_boundary_inference_used",
        "joined_harmonic_labels_authoritative",
        "model_training_started",
        "model_selection_started",
        "full_train_final_fit_started",
        "event_level_training_authorized",
        "production_authority",
        "deterministic_resolver_remains_authoritative",
    )
    summary: dict[str, object] = {"schema_version": SUMMARY_SCHEMA}
    summary.update({field: data[field] for field in fields})

    rendered = json.dumps(summary, sort_keys=True, ensure_ascii=False)
    for private_key in (
        "function_token",
        "phrase_key",
        "carrier_event_id",
        "source_annotation_sha256",
        "carrier_source_order_index",
    ):
        if private_key in rendered:
            raise Stage2GFunctionOnsetEventError(
                "shareable Stage 2-G summary leaks private event data"
            )
    return summary


def run_stage2g_function_onset_events_from_files(
    decisions_path: str | Path,
    archive_path: str | Path,
) -> tuple[dict[str, object], dict[str, object]]:
    require_locked_runtime()
    decision_file = _bounded_regular_file(
        decisions_path,
        max_bytes=MAX_DECISION_BYTES,
        label="validated decisions",
    )
    if decision_file.is_symlink():
        raise Stage2GFunctionOnsetEventError("decision symlink rejected")
    meta = decision_file.stat()
    if not stat.S_ISREG(meta.st_mode):
        raise Stage2GFunctionOnsetEventError(
            "validated decisions must be a regular file"
        )
    raw = decision_file.read_bytes()
    if len(raw) > MAX_DECISION_BYTES:
        raise Stage2GFunctionOnsetEventError(
            "validated decisions exceed size bound"
        )
    decision_data = load_bounded_json(
        decision_file, max_bytes=MAX_DECISION_BYTES
    )
    reviewed_split = build_tavern_reviewed_split_from_file(decision_file)
    private_payload = build_stage2g_function_onset_event_materialization(
        decision_data,
        decision_artifact_sha256=hashlib.sha256(raw).hexdigest(),
        archive_path=archive_path,
        reviewed_split=reviewed_split,
    )
    return private_payload, build_stage2g_summary(private_payload)


def canonical_stage2g_json(data: dict[str, object]) -> str:
    schema = data.get("schema_version")
    if schema == CONTRACT_SCHEMA:
        validate_stage2g_contract(data)
    elif schema == MATERIALIZATION_SCHEMA:
        build_stage2g_summary(data)
    elif schema != SUMMARY_SCHEMA:
        raise Stage2GFunctionOnsetEventError("unsupported Stage 2-G schema")
    return json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ) + "\n"
