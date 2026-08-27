from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import stat
import zipfile
from typing import Any

from .safe_ingest import load_bounded_json
from .stage1e_internal_cv import FOLD_COUNT, PINNED_GROUP_PLAN_SHA256
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
from .stage2e_target_reformulation import (
    build_stage2e_contract,
    validate_stage2e_contract,
)
from .tavern_event_alignment_audit import (
    PINNED_ALIGNMENT_MANIFEST_SHA256,
    TavernEventAlignmentError,
    _event_sequences,
    _joined_member,
)
from .tavern_gold_materialization import PINNED_COUNT, PINNED_VALIDATED_SHA256
from .tavern_normalization_adapter import RECIPROCAL_PREFIX_RE
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

SUMMARY_SCHEMA = "st-stage2f-function-event-carrier-alignment-summary-v1"
CONTRACT_SCHEMA = "st-stage2f-function-event-carrier-alignment-contract-v1"
AUDIT_SCOPE = "STAGE0_T_TRAIN_SELECTED_FUNCTION_ANNOTATIONS_ONLY"
CARRIER_POLICY = "ENCODER_FUNCTION_ROW_TO_ENCODER_HARMONIC_EVENT_TO_JOINED_RECIPROCAL_EVENT"
EXPECTED_TRAIN_RECORD_COUNT = 487
EXPECTED_TRAIN_WORK_FAMILY_COUNT = 18
EXPECTED_FUNCTION_ELIGIBLE_RECORD_COUNT = 478
EXPECTED_FUNCTION_MISSING_RECORD_COUNT = 9
EXPECTED_FUNCTION_SUPPORTED_SOURCE_TARGET_COUNT = 491


class Stage2FFunctionAlignmentError(ValueError):
    pass


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _is_data_token(token: str) -> bool:
    return bool(token) and not token.startswith(("*", "=", "!", "."))


def _reciprocal(token: str) -> str | None:
    match = RECIPROCAL_PREFIX_RE.match(token)
    return match.group(2) if match is not None else None


def parse_function_carrier_rows(raw_text: str) -> dict[str, object]:
    if not isinstance(raw_text, str):
        raise Stage2FFunctionAlignmentError("function carrier source must be text")
    lines = raw_text.splitlines()
    headers = [
        (index, [cell.strip() for cell in line.split("\t")])
        for index, line in enumerate(lines)
        if line.startswith("**")
    ]
    if len(headers) != 1:
        raise Stage2FFunctionAlignmentError(
            f"expected exactly one exclusive-interpretation header, found {len(headers)}"
        )
    header_index, columns = headers[0]
    harmonic_names = [name for name in ("**harm", "**chords") if name in columns]
    if len(harmonic_names) != 1:
        raise Stage2FFunctionAlignmentError(
            "expected exactly one **harm or **chords analysis spine"
        )
    harmonic_index = columns.index(harmonic_names[0])
    function_indices = [i for i, name in enumerate(columns) if name == "**function"]
    if len(function_indices) > 1:
        raise Stage2FFunctionAlignmentError("multiple **function spines are unsupported")
    function_index = function_indices[0] if function_indices else None

    harmonic_durations: list[str | None] = []
    stats: Counter[str] = Counter()
    for line in lines[header_index + 1 :]:
        if not line or line.startswith("!!"):
            continue
        cells = line.split("\t")
        if len(cells) != len(columns):
            stats["row_width_mismatch_count"] += 1
        harmonic = cells[harmonic_index].strip() if harmonic_index < len(cells) else ""
        harmonic_is_data = _is_data_token(harmonic)
        harmonic_reciprocal = _reciprocal(harmonic) if harmonic_is_data else None
        if harmonic_is_data:
            harmonic_durations.append(harmonic_reciprocal)

        if function_index is None:
            continue
        function = cells[function_index].strip() if function_index < len(cells) else ""
        if not _is_data_token(function):
            continue
        stats["function_event_count"] += 1
        function_reciprocal = _reciprocal(function)
        if function_reciprocal is not None:
            stats["function_reciprocal_explicit_count"] += 1
        if harmonic_is_data:
            stats["function_on_harmonic_event_count"] += 1
            if function_reciprocal is not None and harmonic_reciprocal is not None:
                stats["function_harmonic_reciprocal_comparable_count"] += 1
                if function_reciprocal == harmonic_reciprocal:
                    stats["function_harmonic_reciprocal_exact_count"] += 1
                else:
                    stats["function_harmonic_reciprocal_mismatch_count"] += 1
        else:
            stats["function_without_harmonic_event_count"] += 1

    if not harmonic_durations:
        raise Stage2FFunctionAlignmentError("analysis contains no harmonic data events")
    return {
        "harmonic_spine": harmonic_names[0],
        "function_spine_present": function_index is not None,
        "harmonic_event_count": len(harmonic_durations),
        "harmonic_durations": harmonic_durations,
        "harmonic_missing_reciprocal_count": sum(
            duration is None for duration in harmonic_durations
        ),
        "row_width_mismatch_count": stats["row_width_mismatch_count"],
        "function_event_count": stats["function_event_count"],
        "function_on_harmonic_event_count": stats[
            "function_on_harmonic_event_count"
        ],
        "function_without_harmonic_event_count": stats[
            "function_without_harmonic_event_count"
        ],
        "function_reciprocal_explicit_count": stats[
            "function_reciprocal_explicit_count"
        ],
        "function_harmonic_reciprocal_comparable_count": stats[
            "function_harmonic_reciprocal_comparable_count"
        ],
        "function_harmonic_reciprocal_exact_count": stats[
            "function_harmonic_reciprocal_exact_count"
        ],
        "function_harmonic_reciprocal_mismatch_count": stats[
            "function_harmonic_reciprocal_mismatch_count"
        ],
    }


def classify_function_source_path(
    encoder_text: str,
    joined_text: str,
) -> dict[str, object]:
    parsed = parse_function_carrier_rows(encoder_text)
    reasons: set[str] = set()
    function_present = bool(parsed["function_spine_present"])
    function_event_count = int(parsed["function_event_count"])

    try:
        joined_durations, _joined_labels = _event_sequences(
            joined_text,
            accepted_harmonic_spines=("**harm",),
            require_kern_spine=True,
        )
    except TavernEventAlignmentError:
        joined_durations = []
        reasons.add("JOINED_CARRIER_PARSE_FAILED")

    encoder_durations = list(parsed["harmonic_durations"])
    harmonic_sequence_exact = bool(encoder_durations) and (
        encoder_durations == joined_durations
        and int(parsed["harmonic_missing_reciprocal_count"]) == 0
    )
    if not harmonic_sequence_exact:
        reasons.add("ENCODER_JOINED_RECIPROCAL_SEQUENCE_MISMATCH")
    if int(parsed["row_width_mismatch_count"]) != 0:
        reasons.add("ENCODER_ROW_WIDTH_MISMATCH")
    if int(parsed["function_without_harmonic_event_count"]) != 0:
        reasons.add("FUNCTION_EVENT_WITHOUT_HARMONIC_ROW_CARRIER")

    if not function_present:
        status = "FUNCTION_SPINE_MISSING"
    elif function_event_count == 0:
        status = "FUNCTION_EVENTS_MISSING"
    elif reasons:
        status = "QUARANTINE"
    else:
        status = "FUNCTION_ONSET_CARRIER_CANDIDATE"

    duration_exact = (
        status == "FUNCTION_ONSET_CARRIER_CANDIDATE"
        and int(parsed["function_reciprocal_explicit_count"]) == function_event_count
        and int(parsed["function_harmonic_reciprocal_comparable_count"])
        == function_event_count
        and int(parsed["function_harmonic_reciprocal_mismatch_count"]) == 0
    )
    result = {key: value for key, value in parsed.items() if key != "harmonic_durations"}
    result.update(
        {
            "joined_harmonic_event_count": len(joined_durations),
            "encoder_joined_reciprocal_sequence_exact": harmonic_sequence_exact,
            "status": status,
            "duration_exact_single_event_candidate": duration_exact,
            "quarantine_reasons": sorted(reasons),
        }
    )
    return result


def build_stage2f_contract() -> dict[str, object]:
    stage2e = validate_stage2e_contract(build_stage2e_contract())
    function = stage2e["specialists"]["FUNCTION_SPECIALIST"]
    if function["target_decision"] != "RETIRE_WHOLE_PHRASE_CLASSIFICATION_TARGET":
        raise Stage2FFunctionAlignmentError("Stage 2-E Function decision changed")
    if function["next_prerequisite"] != "FUNCTION_EVENT_CARRIER_ALIGNMENT_AUDIT_REQUIRED":
        raise Stage2FFunctionAlignmentError("Stage 2-E Function prerequisite changed")
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
        "eligible_original_partition": "TRAIN",
        "record_count": EXPECTED_TRAIN_RECORD_COUNT,
        "work_family_count": EXPECTED_TRAIN_WORK_FAMILY_COUNT,
        "source_target_slot_count": PINNED_STAGE2B_SOURCE_TARGET_SLOT_COUNT,
        "expected_function_eligible_record_count": EXPECTED_FUNCTION_ELIGIBLE_RECORD_COUNT,
        "expected_function_supported_source_target_count": (
            EXPECTED_FUNCTION_SUPPORTED_SOURCE_TARGET_COUNT
        ),
        "audit_scope": AUDIT_SCOPE,
        "carrier_policy": CARRIER_POLICY,
        "joined_harmonic_labels_authoritative": False,
        "function_target_values_serialized": False,
        "record_diagnostics_serialized": False,
        "target_shape_decision_authorized": False,
        "event_target_materialization_authorized": False,
        "model_fitting_authorized": False,
        "model_selection_authorized": False,
        "full_train_final_fit_authorized": False,
        "event_level_training_authorized": False,
        "original_validation_target_access": False,
        "calibration_target_access": False,
        "holdout_target_access": False,
        "stage1d_quarantine_reuse_authorized": False,
        "production_authority": False,
        "deterministic_resolver_remains_authoritative": True,
    }


def validate_stage2f_contract(data: object) -> dict[str, Any]:
    expected = build_stage2f_contract()
    if not isinstance(data, dict) or data != expected:
        raise Stage2FFunctionAlignmentError(
            "Stage 2-F contract differs from frozen alignment contract"
        )
    return data


def _increment_path_stats(stats: Counter[str], diagnostic: dict[str, object]) -> None:
    stats["selected_source_path_count"] += 1
    for field in (
        "harmonic_event_count",
        "function_event_count",
        "function_on_harmonic_event_count",
        "function_without_harmonic_event_count",
        "function_reciprocal_explicit_count",
        "function_harmonic_reciprocal_comparable_count",
        "function_harmonic_reciprocal_exact_count",
        "function_harmonic_reciprocal_mismatch_count",
    ):
        stats[field] += int(diagnostic[field])
    stats["function_spine_present_source_path_count"] += int(
        diagnostic["function_spine_present"] is True
    )
    stats["joined_harmonic_alignment_exact_source_path_count"] += int(
        diagnostic["encoder_joined_reciprocal_sequence_exact"] is True
    )
    stats["onset_carrier_candidate_source_path_count"] += int(
        diagnostic["status"] == "FUNCTION_ONSET_CARRIER_CANDIDATE"
    )
    stats["duration_exact_source_path_count"] += int(
        diagnostic["duration_exact_single_event_candidate"] is True
    )
    stats["quarantine_source_path_count"] += int(diagnostic["status"] == "QUARANTINE")
    stats["missing_function_source_path_count"] += int(
        diagnostic["status"] in {"FUNCTION_SPINE_MISSING", "FUNCTION_EVENTS_MISSING"}
    )


def build_stage2f_function_alignment_summary(
    decision_data: object,
    *,
    decision_artifact_sha256: str,
    archive_path: str | Path,
    reviewed_split: object,
) -> dict[str, object]:
    validate_stage2f_contract(build_stage2f_contract())
    decisions = _validate_decision_data(
        decision_data,
        artifact_sha256=decision_artifact_sha256,
        expected_artifact_sha256=PINNED_VALIDATED_SHA256,
        expected_count=PINNED_COUNT,
    )
    train_identity = build_train_identity_map(reviewed_split)
    decision_by_phrase = {str(item["phrase_key"]): item for item in decisions}
    if not set(train_identity).issubset(decision_by_phrase):
        raise Stage2FFunctionAlignmentError(
            "TRAIN identity set is not covered by validated decisions"
        )

    archive_file = _bounded_regular_file(
        archive_path, max_bytes=MAX_ARCHIVE_BYTES, label="archive"
    )
    archive_sha256 = _sha256_file(archive_file)
    if archive_sha256 != PINNED_TAVERN_ARCHIVE_SHA256:
        raise Stage2FFunctionAlignmentError("TAVERN archive SHA-256 mismatch")

    stats: Counter[str] = Counter()
    fold_records: Counter[int] = Counter()
    fold_eligible: Counter[int] = Counter()
    fold_candidates: Counter[int] = Counter()
    fold_groups: dict[int, set[str]] = defaultdict(set)
    diagnostic_manifest_rows: list[dict[str, object]] = []
    parsed_annotation_phrases: set[str] = set()

    try:
        with zipfile.ZipFile(archive_file) as archive:
            infos = _validated_zip_members(archive)
            corrupt = archive.testzip()
            if corrupt is not None:
                raise Stage2FFunctionAlignmentError(f"corrupt archive member: {corrupt}")
            root = _archive_root(infos)

            for phrase in sorted(train_identity):
                identity = train_identity[phrase]
                decision = decision_by_phrase[phrase]
                fold = int(identity["development_fold"])
                group = str(identity["split_group_id"])
                fold_records[fold] += 1
                fold_groups[fold].add(group)
                path_diagnostics: list[dict[str, object]] = []

                for source, expected_hash in _selected_sources(decision):
                    encoder_info = _selected_member(infos, phrase, source)
                    if encoder_info.file_size > MAX_LABEL_BYTES:
                        raise Stage2FFunctionAlignmentError(
                            f"TRAIN annotation exceeds size bound: {phrase}/{source}"
                        )
                    encoder_raw = archive.read(encoder_info)
                    if hashlib.sha256(encoder_raw).hexdigest() != expected_hash:
                        raise Stage2FFunctionAlignmentError(
                            f"TRAIN annotation SHA-256 mismatch: {phrase}/{source}"
                        )
                    joined_info = _joined_member(
                        infos, root=root, phrase_key=phrase, source=source
                    )
                    joined_raw = archive.read(joined_info)
                    try:
                        encoder_text = encoder_raw.decode("utf-8", errors="strict")
                        joined_text = joined_raw.decode("utf-8", errors="strict")
                    except UnicodeDecodeError as exc:
                        raise Stage2FFunctionAlignmentError(
                            f"TRAIN alignment source is not UTF-8: {phrase}/{source}"
                        ) from exc
                    diagnostic = classify_function_source_path(encoder_text, joined_text)
                    _increment_path_stats(stats, diagnostic)
                    diagnostic_manifest_rows.append(
                        {
                            "phrase_key": phrase,
                            "source": source,
                            "development_fold": fold,
                            "status": diagnostic["status"],
                            "function_event_count": diagnostic["function_event_count"],
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
                    path_diagnostics.append(diagnostic)

                parsed_annotation_phrases.add(phrase)
                has_function = all(
                    int(item["function_event_count"]) > 0 for item in path_diagnostics
                )
                if has_function:
                    stats["function_eligible_record_count"] += 1
                    fold_eligible[fold] += 1
                    if all(
                        item["status"] == "FUNCTION_ONSET_CARRIER_CANDIDATE"
                        for item in path_diagnostics
                    ):
                        stats["onset_carrier_candidate_record_count"] += 1
                        fold_candidates[fold] += 1
                    else:
                        stats["quarantine_record_count"] += 1
                else:
                    stats["missing_function_record_count"] += 1
    except zipfile.BadZipFile as exc:
        raise Stage2FFunctionAlignmentError("invalid TAVERN ZIP archive") from exc

    if parsed_annotation_phrases != set(train_identity):
        raise Stage2FFunctionAlignmentError(
            "annotation parse scope differs from TRAIN identity set"
        )
    if stats["selected_source_path_count"] != PINNED_STAGE2B_SOURCE_TARGET_SLOT_COUNT:
        raise Stage2FFunctionAlignmentError("selected TRAIN source-slot count changed")
    if stats["function_eligible_record_count"] != EXPECTED_FUNCTION_ELIGIBLE_RECORD_COUNT:
        raise Stage2FFunctionAlignmentError("Function eligible TRAIN record count changed")
    if stats["missing_function_record_count"] != EXPECTED_FUNCTION_MISSING_RECORD_COUNT:
        raise Stage2FFunctionAlignmentError("Function missing TRAIN record count changed")
    supported_source_targets = (
        stats["selected_source_path_count"] - stats["missing_function_source_path_count"]
    )
    if supported_source_targets != EXPECTED_FUNCTION_SUPPORTED_SOURCE_TARGET_COUNT:
        raise Stage2FFunctionAlignmentError("Function supported source-target count changed")

    record_distribution = {str(i): fold_records[i] for i in range(FOLD_COUNT)}
    eligible_distribution = {str(i): fold_eligible[i] for i in range(FOLD_COUNT)}
    candidate_distribution = {str(i): fold_candidates[i] for i in range(FOLD_COUNT)}
    work_family_distribution = {str(i): len(fold_groups[i]) for i in range(FOLD_COUNT)}
    if work_family_distribution != {str(i): 6 for i in range(FOLD_COUNT)}:
        raise Stage2FFunctionAlignmentError("TRAIN work-family fold distribution changed")

    diagnostic_manifest_rows.sort(
        key=lambda item: (str(item["phrase_key"]), str(item["source"]))
    )
    return {
        "schema_version": SUMMARY_SCHEMA,
        "source_corpus": SOURCE_CORPUS,
        "source_revision": PINNED_TAVERN_REVISION,
        "validated_human_decisions_sha256": decision_artifact_sha256,
        "archive_sha256": archive_sha256,
        "source_stage1d_alignment_manifest_sha256": PINNED_ALIGNMENT_MANIFEST_SHA256,
        "source_stage1e_group_plan_manifest_sha256": PINNED_GROUP_PLAN_SHA256,
        "source_stage2b_private_record_manifest_sha256": (
            PINNED_STAGE2B_PRIVATE_RECORD_MANIFEST_SHA256
        ),
        "audit_scope": AUDIT_SCOPE,
        "carrier_policy": CARRIER_POLICY,
        "record_count": EXPECTED_TRAIN_RECORD_COUNT,
        "work_family_count": EXPECTED_TRAIN_WORK_FAMILY_COUNT,
        "fold_count": FOLD_COUNT,
        "fold_record_distribution": record_distribution,
        "fold_work_family_distribution": work_family_distribution,
        "fold_function_eligible_record_distribution": eligible_distribution,
        "fold_onset_carrier_candidate_record_distribution": candidate_distribution,
        "selected_source_path_count": stats["selected_source_path_count"],
        "function_supported_source_target_count": supported_source_targets,
        "function_eligible_record_count": stats["function_eligible_record_count"],
        "missing_function_record_count": stats["missing_function_record_count"],
        "onset_carrier_candidate_record_count": stats[
            "onset_carrier_candidate_record_count"
        ],
        "quarantine_record_count": stats["quarantine_record_count"],
        "function_spine_present_source_path_count": stats[
            "function_spine_present_source_path_count"
        ],
        "missing_function_source_path_count": stats["missing_function_source_path_count"],
        "joined_harmonic_alignment_exact_source_path_count": stats[
            "joined_harmonic_alignment_exact_source_path_count"
        ],
        "onset_carrier_candidate_source_path_count": stats[
            "onset_carrier_candidate_source_path_count"
        ],
        "duration_exact_source_path_count": stats["duration_exact_source_path_count"],
        "quarantine_source_path_count": stats["quarantine_source_path_count"],
        "harmonic_event_count": stats["harmonic_event_count"],
        "function_event_count": stats["function_event_count"],
        "function_on_harmonic_event_count": stats[
            "function_on_harmonic_event_count"
        ],
        "function_without_harmonic_event_count": stats[
            "function_without_harmonic_event_count"
        ],
        "function_reciprocal_explicit_count": stats[
            "function_reciprocal_explicit_count"
        ],
        "function_harmonic_reciprocal_comparable_count": stats[
            "function_harmonic_reciprocal_comparable_count"
        ],
        "function_harmonic_reciprocal_exact_count": stats[
            "function_harmonic_reciprocal_exact_count"
        ],
        "function_harmonic_reciprocal_mismatch_count": stats[
            "function_harmonic_reciprocal_mismatch_count"
        ],
        "diagnostic_manifest_sha256": _canonical_sha256(diagnostic_manifest_rows),
        "diagnostic_rows_serialized": False,
        "function_target_values_serialized": False,
        "joined_harmonic_labels_authoritative": False,
        "target_shape_decision_authorized": False,
        "event_target_materialization_authorized": False,
        "model_fitting_started": False,
        "model_selection_started": False,
        "full_train_final_fit_started": False,
        "event_level_training_authorized": False,
        "non_train_annotation_bodies_materialized": False,
        "original_validation_target_access": False,
        "calibration_target_access": False,
        "holdout_target_access": False,
        "stage1d_quarantine_reuse_authorized": False,
        "production_authority": False,
        "deterministic_resolver_remains_authoritative": True,
    }


def validate_stage2f_summary(data: object) -> dict[str, Any]:
    if not isinstance(data, dict) or data.get("schema_version") != SUMMARY_SCHEMA:
        raise Stage2FFunctionAlignmentError("unsupported Stage 2-F summary schema")
    expected = {
        "source_corpus": SOURCE_CORPUS,
        "source_revision": PINNED_TAVERN_REVISION,
        "validated_human_decisions_sha256": PINNED_VALIDATED_SHA256,
        "archive_sha256": PINNED_TAVERN_ARCHIVE_SHA256,
        "source_stage1d_alignment_manifest_sha256": PINNED_ALIGNMENT_MANIFEST_SHA256,
        "source_stage1e_group_plan_manifest_sha256": PINNED_GROUP_PLAN_SHA256,
        "source_stage2b_private_record_manifest_sha256": (
            PINNED_STAGE2B_PRIVATE_RECORD_MANIFEST_SHA256
        ),
        "audit_scope": AUDIT_SCOPE,
        "carrier_policy": CARRIER_POLICY,
        "record_count": EXPECTED_TRAIN_RECORD_COUNT,
        "work_family_count": EXPECTED_TRAIN_WORK_FAMILY_COUNT,
        "fold_count": FOLD_COUNT,
        "selected_source_path_count": PINNED_STAGE2B_SOURCE_TARGET_SLOT_COUNT,
        "function_supported_source_target_count": (
            EXPECTED_FUNCTION_SUPPORTED_SOURCE_TARGET_COUNT
        ),
        "function_eligible_record_count": EXPECTED_FUNCTION_ELIGIBLE_RECORD_COUNT,
        "missing_function_record_count": EXPECTED_FUNCTION_MISSING_RECORD_COUNT,
        "diagnostic_rows_serialized": False,
        "function_target_values_serialized": False,
        "joined_harmonic_labels_authoritative": False,
        "target_shape_decision_authorized": False,
        "event_target_materialization_authorized": False,
        "model_fitting_started": False,
        "model_selection_started": False,
        "full_train_final_fit_started": False,
        "event_level_training_authorized": False,
        "non_train_annotation_bodies_materialized": False,
        "original_validation_target_access": False,
        "calibration_target_access": False,
        "holdout_target_access": False,
        "stage1d_quarantine_reuse_authorized": False,
        "production_authority": False,
        "deterministic_resolver_remains_authoritative": True,
    }
    for field, value in expected.items():
        if data.get(field) != value:
            raise Stage2FFunctionAlignmentError(
                f"Stage 2-F summary boundary changed: {field}"
            )
    candidate = data.get("onset_carrier_candidate_record_count")
    quarantine = data.get("quarantine_record_count")
    if not isinstance(candidate, int) or not isinstance(quarantine, int):
        raise Stage2FFunctionAlignmentError("Stage 2-F record outcome counts malformed")
    if candidate + quarantine != EXPECTED_FUNCTION_ELIGIBLE_RECORD_COUNT:
        raise Stage2FFunctionAlignmentError(
            "Stage 2-F eligible record outcomes do not close"
        )
    for field in (
        "function_event_count",
        "function_on_harmonic_event_count",
        "function_without_harmonic_event_count",
        "onset_carrier_candidate_source_path_count",
        "duration_exact_source_path_count",
    ):
        if not isinstance(data.get(field), int) or int(data[field]) < 0:
            raise Stage2FFunctionAlignmentError(f"invalid Stage 2-F count: {field}")
    if int(data["function_on_harmonic_event_count"]) > int(data["function_event_count"]):
        raise Stage2FFunctionAlignmentError("aligned Function event count exceeds total")
    if int(data["duration_exact_source_path_count"]) > int(
        data["onset_carrier_candidate_source_path_count"]
    ):
        raise Stage2FFunctionAlignmentError("duration-exact paths exceed onset candidates")
    return data


def run_stage2f_function_alignment_from_files(
    decisions_path: str | Path,
    archive_path: str | Path,
) -> dict[str, object]:
    decision_file = _bounded_regular_file(
        decisions_path, max_bytes=MAX_DECISION_BYTES, label="validated decisions"
    )
    if decision_file.is_symlink():
        raise Stage2FFunctionAlignmentError("decision symlink rejected")
    meta = decision_file.stat()
    if not stat.S_ISREG(meta.st_mode):
        raise Stage2FFunctionAlignmentError("decision input must be regular file")
    raw = decision_file.read_bytes()
    if len(raw) > MAX_DECISION_BYTES:
        raise Stage2FFunctionAlignmentError("decision input exceeds size bound")
    decision_data = load_bounded_json(decision_file, max_bytes=MAX_DECISION_BYTES)
    reviewed_split = build_tavern_reviewed_split_from_file(decision_file)
    summary = build_stage2f_function_alignment_summary(
        decision_data,
        decision_artifact_sha256=hashlib.sha256(raw).hexdigest(),
        archive_path=archive_path,
        reviewed_split=reviewed_split,
    )
    validate_stage2f_summary(summary)
    return summary


def canonical_stage2f_json(data: dict[str, object]) -> str:
    if data.get("schema_version") == CONTRACT_SCHEMA:
        validate_stage2f_contract(data)
    elif data.get("schema_version") == SUMMARY_SCHEMA:
        validate_stage2f_summary(data)
    else:
        raise Stage2FFunctionAlignmentError("unsupported Stage 2-F schema")
    return json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ) + "\n"
