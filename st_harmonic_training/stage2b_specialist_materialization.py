from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import stat
import zipfile
from typing import Any

from .normalization import NORMALIZATION_VERSION, build_normalization_record
from .safe_ingest import load_bounded_json
from .specialist_contract import build_specialist_contract, validate_specialist_contract
from .stage1e_internal_cv import (
    FOLD_COUNT,
    PINNED_GROUP_PLAN_SHA256,
    EXPECTED_TRAIN_RECORD_COUNT,
    EXPECTED_TRAIN_WORK_FAMILY_COUNT,
    build_stage1e_group_plan,
)
from .tavern_adjudication import ADJUDICATION_INPUT_SCHEMA
from .tavern_gold_materialization import PINNED_COUNT, PINNED_VALIDATED_SHA256
from .tavern_kern_features import ADAPTER_VERSION as FEATURE_ADAPTER_VERSION
from .tavern_kern_features import extract_kern_bow_features
from .tavern_normalization_adapter import parse_tavern_analysis_label
from .tavern_raw_label_realization import (
    MAX_ARCHIVE_BYTES,
    MAX_DECISION_BYTES,
    MAX_LABEL_BYTES,
    PINNED_TAVERN_ARCHIVE_SHA256,
    SHA256_RE,
    _bounded_regular_file,
    _selected_member,
    _selected_sources,
    _validated_zip_members,
)
from .tavern_reviewed_split import (
    EXPECTED_RECORD_DISTRIBUTION,
    SPLIT_SCHEMA,
    build_tavern_reviewed_split_from_file,
)
from .tavern_score_input_realization import (
    MAX_SCORE_BYTES,
    _archive_root,
    _score_inventory_digest,
    _score_member,
)
from .tavern_structure import PINNED_TAVERN_REVISION
from .tavern_subset_admission import SCORE_SHA256

MATERIALIZATION_SCHEMA = "st-stage2b-specialist-train-materialization-v1"
SUMMARY_SCHEMA = "st-stage2b-specialist-train-summary-v1"
SOURCE_CORPUS = "TAVERN_REVIEWED_694"
TARGET_SET_POLICY = "CANONICAL_NORMALIZED_UNIQUE_NON_NULL_SET"
ANNOTATION_PARSE_SCOPE = "TRAIN_ONLY"
SCORE_FEATURE_SCOPE = "TRAIN_ONLY"
MAX_PRIVATE_OUTPUT_RECORDS = EXPECTED_TRAIN_RECORD_COUNT

SPECIALIST_FIELDS = (
    ("ROMAN_NUMERAL_SPECIALIST", "roman_numeral"),
    ("KEY_SPECIALIST", "key"),
    ("FUNCTION_SPECIALIST", "phrase"),
)


class Stage2BSpecialistMaterializationError(ValueError):
    pass


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _validate_stage2a_contract() -> None:
    contract = validate_specialist_contract(build_specialist_contract())
    observed = tuple(
        (str(item["specialist_id"]), str(item["target_field"]))
        for item in contract["first_wave_specialists"]
    )
    if observed != SPECIALIST_FIELDS:
        raise Stage2BSpecialistMaterializationError(
            "Stage 2-A first-wave specialist contract changed"
        )
    for field in (
        "training_authorized",
        "calibration_access_authorized",
        "holdout_access_authorized",
        "event_level_training_authorized",
        "production_authority",
    ):
        if contract.get(field) is not False:
            raise Stage2BSpecialistMaterializationError(
                f"Stage 2-A authority boundary changed: {field}"
            )


def _validate_decision_data(
    data: object,
    *,
    artifact_sha256: str,
    expected_artifact_sha256: str = PINNED_VALIDATED_SHA256,
    expected_count: int = PINNED_COUNT,
) -> list[dict[str, Any]]:
    if artifact_sha256 != expected_artifact_sha256:
        raise Stage2BSpecialistMaterializationError(
            "validated decision artifact SHA-256 mismatch"
        )
    if not isinstance(data, dict) or data.get("schema_version") != ADJUDICATION_INPUT_SCHEMA:
        raise Stage2BSpecialistMaterializationError("unsupported decision schema")
    if data.get("source_corpus") != "TAVERN":
        raise Stage2BSpecialistMaterializationError("decision source corpus mismatch")
    if data.get("source_revision") != PINNED_TAVERN_REVISION:
        raise Stage2BSpecialistMaterializationError("decision source revision mismatch")
    if data.get("reviewer_type") != "HUMAN":
        raise Stage2BSpecialistMaterializationError("human reviewer required")
    decisions = data.get("decisions")
    if not isinstance(decisions, list) or not all(isinstance(item, dict) for item in decisions):
        raise Stage2BSpecialistMaterializationError("decision rows malformed")
    if len(decisions) != expected_count:
        raise Stage2BSpecialistMaterializationError("decision count mismatch")
    seen: set[str] = set()
    for item in decisions:
        phrase = item.get("phrase_key")
        if not isinstance(phrase, str) or not phrase:
            raise Stage2BSpecialistMaterializationError("decision phrase_key missing")
        if phrase in seen:
            raise Stage2BSpecialistMaterializationError(f"duplicate phrase_key: {phrase}")
        seen.add(phrase)
        # Validate decision/source shape before any annotation body is opened.
        selected = _selected_sources(item)
        if len(selected) not in {1, 2}:
            raise Stage2BSpecialistMaterializationError(
                f"unexpected selected-source count: {phrase}"
            )
        for source, digest in selected:
            if source not in {"A", "B"} or SHA256_RE.fullmatch(digest) is None:
                raise Stage2BSpecialistMaterializationError(
                    f"invalid selected source/hash: {phrase}/{source}"
                )
    return decisions


def build_train_identity_map(
    reviewed_split: object,
    *,
    expected_train_record_count: int = EXPECTED_TRAIN_RECORD_COUNT,
    expected_record_distribution: dict[str, int] | None = None,
    group_plan: object | None = None,
) -> dict[str, dict[str, object]]:
    if expected_record_distribution is None:
        expected_record_distribution = EXPECTED_RECORD_DISTRIBUTION
    if not isinstance(reviewed_split, dict) or reviewed_split.get("schema_version") != SPLIT_SCHEMA:
        raise Stage2BSpecialistMaterializationError("unsupported reviewed split schema")
    if reviewed_split.get("source_corpus") != SOURCE_CORPUS:
        raise Stage2BSpecialistMaterializationError("reviewed split source mismatch")
    if reviewed_split.get("source_revision") != PINNED_TAVERN_REVISION:
        raise Stage2BSpecialistMaterializationError("reviewed split revision mismatch")
    if reviewed_split.get("record_distribution") != expected_record_distribution:
        raise Stage2BSpecialistMaterializationError("reviewed split distribution changed")
    if reviewed_split.get("training_authorized") is not False:
        raise Stage2BSpecialistMaterializationError(
            "reviewed split unexpectedly authorizes training"
        )
    records = reviewed_split.get("records")
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        raise Stage2BSpecialistMaterializationError("reviewed split rows malformed")

    if group_plan is None:
        group_plan = build_stage1e_group_plan()
    if not isinstance(group_plan, dict):
        raise Stage2BSpecialistMaterializationError("Stage 1-E group plan malformed")
    if group_plan.get("group_plan_manifest_sha256") != PINNED_GROUP_PLAN_SHA256:
        raise Stage2BSpecialistMaterializationError("Stage 1-E group plan digest changed")
    if group_plan.get("fold_count") != FOLD_COUNT:
        raise Stage2BSpecialistMaterializationError("Stage 1-E fold count changed")
    if group_plan.get("eligible_partition") != "TRAIN":
        raise Stage2BSpecialistMaterializationError("Stage 1-E eligible partition changed")
    for field in (
        "original_validation_access",
        "calibration_access",
        "holdout_access",
        "training_authorized",
        "production_authority",
    ):
        if group_plan.get(field) is not False:
            raise Stage2BSpecialistMaterializationError(
                f"Stage 1-E authority boundary changed: {field}"
            )
    groups = group_plan.get("groups")
    if not isinstance(groups, list) or not all(isinstance(item, dict) for item in groups):
        raise Stage2BSpecialistMaterializationError("Stage 1-E group rows malformed")
    fold_by_group: dict[str, int] = {}
    for item in groups:
        group = item.get("split_group_id")
        fold = item.get("development_fold")
        if not isinstance(group, str) or not group or not isinstance(fold, int):
            raise Stage2BSpecialistMaterializationError("invalid Stage 1-E group assignment")
        if fold < 0 or fold >= FOLD_COUNT or group in fold_by_group:
            raise Stage2BSpecialistMaterializationError("invalid/duplicate Stage 1-E group")
        fold_by_group[group] = fold
    if len(fold_by_group) != EXPECTED_TRAIN_WORK_FAMILY_COUNT:
        raise Stage2BSpecialistMaterializationError("TRAIN work-family plan changed")

    train: dict[str, dict[str, object]] = {}
    seen_all: set[str] = set()
    source_counts: Counter[str] = Counter()
    for item in records:
        phrase = item.get("phrase_key")
        partition = item.get("partition")
        group = item.get("split_group_id")
        canonical = item.get("canonical_work_id")
        source_work = item.get("source_work_id")
        if not isinstance(phrase, str) or not phrase or phrase in seen_all:
            raise Stage2BSpecialistMaterializationError("invalid/duplicate split phrase")
        seen_all.add(phrase)
        if partition not in {"TRAIN", "VALIDATION", "CALIBRATION", "HOLDOUT"}:
            raise Stage2BSpecialistMaterializationError("unsupported original partition")
        source_counts[str(partition)] += 1
        if partition != "TRAIN":
            continue
        if not isinstance(group, str) or group not in fold_by_group:
            raise Stage2BSpecialistMaterializationError(
                f"TRAIN phrase has unknown Stage 1-E group: {phrase}"
            )
        if canonical != group:
            raise Stage2BSpecialistMaterializationError(
                f"canonical/split-group mismatch: {phrase}"
            )
        if not isinstance(source_work, str) or not phrase.startswith(f"{source_work}:"):
            raise Stage2BSpecialistMaterializationError(
                f"source-work/phrase mismatch: {phrase}"
            )
        train[phrase] = {
            "source_work_id": source_work,
            "canonical_work_id": canonical,
            "split_group_id": group,
            "development_fold": fold_by_group[group],
        }

    observed_counts = {key: source_counts[key] for key in sorted(source_counts)}
    if observed_counts != expected_record_distribution:
        raise Stage2BSpecialistMaterializationError(
            "observed reviewed-split partition counts changed"
        )
    if len(train) != expected_train_record_count:
        raise Stage2BSpecialistMaterializationError("TRAIN record count changed")
    train_groups = {str(item["split_group_id"]) for item in train.values()}
    if train_groups != set(fold_by_group):
        raise Stage2BSpecialistMaterializationError("TRAIN work-family set changed")
    return train


def project_specialist_targets(
    source_rows: list[dict[str, object]],
) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for specialist_id, field in SPECIALIST_FIELDS:
        source_targets: list[dict[str, object]] = []
        effective_targets: list[str] = []
        seen_effective: set[str] = set()
        for row in source_rows:
            source = row.get("source")
            normalized = row.get("normalized_st_label")
            if source not in {"A", "B"} or not isinstance(normalized, dict):
                raise Stage2BSpecialistMaterializationError(
                    "specialist source row malformed"
                )
            value = normalized.get(field)
            if value is not None and not isinstance(value, str):
                raise Stage2BSpecialistMaterializationError(
                    f"specialist target must be string/null: {specialist_id}"
                )
            source_targets.append({"source": source, "value": value})
            if value is not None and value not in seen_effective:
                seen_effective.add(value)
                effective_targets.append(value)
        source_targets.sort(key=lambda item: str(item["source"]))
        effective_targets.sort()
        result[specialist_id] = {
            "target_field": field,
            "source_targets": source_targets,
            "effective_targets": effective_targets,
        }
    return result


def _normalize_selected_label(raw: bytes) -> dict[str, object]:
    try:
        raw_text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise Stage2BSpecialistMaterializationError(
            "selected TRAIN annotation is not UTF-8"
        ) from exc
    mapping, _metadata = parse_tavern_analysis_label(raw_text)
    normalized = build_normalization_record(
        raw_text, mapping, normalization_version=NORMALIZATION_VERSION
    ).normalized_st_label.to_dict()
    return normalized


def build_stage2b_specialist_materialization(
    decision_data: object,
    *,
    decision_artifact_sha256: str,
    archive_path: str | Path,
    reviewed_split: object,
    expected_archive_sha256: str = PINNED_TAVERN_ARCHIVE_SHA256,
    expected_score_inventory_sha256: str = SCORE_SHA256,
) -> dict[str, object]:
    _validate_stage2a_contract()
    decisions = _validate_decision_data(
        decision_data, artifact_sha256=decision_artifact_sha256
    )
    train_identity = build_train_identity_map(reviewed_split)
    decision_by_phrase = {str(item["phrase_key"]): item for item in decisions}
    if not set(train_identity).issubset(decision_by_phrase):
        raise Stage2BSpecialistMaterializationError(
            "TRAIN identity set is not covered by validated decisions"
        )

    archive_file = _bounded_regular_file(
        archive_path, max_bytes=MAX_ARCHIVE_BYTES, label="archive"
    )
    archive_sha256 = _sha256_file(archive_file)
    if archive_sha256 != expected_archive_sha256:
        raise Stage2BSpecialistMaterializationError("TAVERN archive SHA-256 mismatch")

    records: list[dict[str, object]] = []
    feature_vocabulary: set[str] = set()
    feature_occurrence_count = 0
    source_target_slot_count = 0
    specialist_supported_source_targets: Counter[str] = Counter()
    specialist_effective_targets: Counter[str] = Counter()
    specialist_eligible_records: Counter[str] = Counter()
    fold_records: Counter[int] = Counter()
    fold_groups: dict[int, set[str]] = defaultdict(set)
    parsed_annotation_phrases: set[str] = set()
    parsed_annotation_members: set[str] = set()

    try:
        with zipfile.ZipFile(archive_file) as archive:
            infos = _validated_zip_members(archive)
            root = _archive_root(infos)
            inventory_sha256, inventory_count = _score_inventory_digest(
                archive, infos, root=root
            )
            if inventory_sha256 != expected_score_inventory_sha256:
                raise Stage2BSpecialistMaterializationError(
                    "TAVERN score inventory SHA-256 mismatch"
                )

            for phrase in sorted(train_identity):
                identity = train_identity[phrase]
                decision = decision_by_phrase[phrase]
                selected_rows: list[dict[str, object]] = []
                for source, expected_hash in _selected_sources(decision):
                    info = _selected_member(infos, phrase, source)
                    if info.file_size > MAX_LABEL_BYTES:
                        raise Stage2BSpecialistMaterializationError(
                            f"TRAIN annotation exceeds size bound: {phrase}/{source}"
                        )
                    raw = archive.read(info)
                    actual_hash = hashlib.sha256(raw).hexdigest()
                    if actual_hash != expected_hash:
                        raise Stage2BSpecialistMaterializationError(
                            f"TRAIN annotation SHA-256 mismatch: {phrase}/{source}"
                        )
                    normalized = _normalize_selected_label(raw)
                    selected_rows.append(
                        {
                            "source": source,
                            "raw_sha256": actual_hash,
                            "normalized_st_label": normalized,
                        }
                    )
                    parsed_annotation_members.add(info.filename)
                    source_target_slot_count += 1
                parsed_annotation_phrases.add(phrase)

                score_info = _score_member(infos, root=root, phrase_key=phrase)
                if score_info.file_size > MAX_SCORE_BYTES:
                    raise Stage2BSpecialistMaterializationError(
                        f"TRAIN score exceeds size bound: {phrase}"
                    )
                score_raw = archive.read(score_info)
                if len(score_raw) != score_info.file_size:
                    raise Stage2BSpecialistMaterializationError(
                        f"TRAIN score size mismatch: {phrase}"
                    )
                try:
                    score_text = score_raw.decode("utf-8", errors="strict")
                except UnicodeDecodeError as exc:
                    raise Stage2BSpecialistMaterializationError(
                        f"TRAIN score is not UTF-8: {phrase}"
                    ) from exc
                features, _feature_stats = extract_kern_bow_features(score_text)
                feature_vocabulary.update(features)
                feature_occurrence_count += sum(features.values())
                feature_sha256 = hashlib.sha256(_canonical_bytes(features)).hexdigest()
                score_sha256 = hashlib.sha256(score_raw).hexdigest()

                specialists = project_specialist_targets(selected_rows)
                for specialist_id, payload in specialists.items():
                    source_targets = payload["source_targets"]
                    effective_targets = payload["effective_targets"]
                    specialist_supported_source_targets[specialist_id] += sum(
                        1 for item in source_targets if item["value"] is not None
                    )
                    specialist_effective_targets[specialist_id] += len(effective_targets)
                    if effective_targets:
                        specialist_eligible_records[specialist_id] += 1

                fold = int(identity["development_fold"])
                group = str(identity["split_group_id"])
                fold_records[fold] += 1
                fold_groups[fold].add(group)
                records.append(
                    {
                        "phrase_key": phrase,
                        "source_work_id": identity["source_work_id"],
                        "canonical_work_id": identity["canonical_work_id"],
                        "split_group_id": group,
                        "development_fold": fold,
                        "score_sha256": score_sha256,
                        "feature_adapter_version": FEATURE_ADAPTER_VERSION,
                        "feature_sha256": feature_sha256,
                        "features": features,
                        "specialists": specialists,
                    }
                )
    except zipfile.BadZipFile as exc:
        raise Stage2BSpecialistMaterializationError("invalid TAVERN ZIP archive") from exc

    if parsed_annotation_phrases != set(train_identity):
        raise Stage2BSpecialistMaterializationError(
            "annotation parse scope differs from TRAIN identity set"
        )
    if len(records) != EXPECTED_TRAIN_RECORD_COUNT:
        raise Stage2BSpecialistMaterializationError("materialized TRAIN record count changed")
    if len(records) > MAX_PRIVATE_OUTPUT_RECORDS:
        raise Stage2BSpecialistMaterializationError("private output record bound exceeded")

    # A source annotation member may serve only its selected TRAIN phrase/source.
    if len(parsed_annotation_members) != source_target_slot_count:
        raise Stage2BSpecialistMaterializationError(
            "TRAIN annotation member reuse/duplication detected"
        )

    fold_record_distribution = {
        str(index): fold_records[index] for index in range(FOLD_COUNT)
    }
    fold_work_family_distribution = {
        str(index): len(fold_groups[index]) for index in range(FOLD_COUNT)
    }
    if any(value == 0 for value in fold_record_distribution.values()):
        raise Stage2BSpecialistMaterializationError("empty Stage 2-B development fold")
    if fold_work_family_distribution != {str(index): 6 for index in range(FOLD_COUNT)}:
        raise Stage2BSpecialistMaterializationError(
            "Stage 2-B work-family fold distribution changed"
        )

    records.sort(key=lambda item: str(item["phrase_key"]))
    specialist_support: dict[str, dict[str, int]] = {}
    for specialist_id, _field in SPECIALIST_FIELDS:
        eligible = specialist_eligible_records[specialist_id]
        specialist_support[specialist_id] = {
            "supported_source_target_count": specialist_supported_source_targets[
                specialist_id
            ],
            "effective_target_count": specialist_effective_targets[specialist_id],
            "eligible_record_count": eligible,
            "missing_record_count": EXPECTED_TRAIN_RECORD_COUNT - eligible,
        }

    return {
        "schema_version": MATERIALIZATION_SCHEMA,
        "source_corpus": SOURCE_CORPUS,
        "source_revision": PINNED_TAVERN_REVISION,
        "validated_human_decisions_sha256": decision_artifact_sha256,
        "archive_sha256": archive_sha256,
        "score_inventory_sha256": expected_score_inventory_sha256,
        "score_inventory_member_count": inventory_count,
        "eligible_original_partition": "TRAIN",
        "record_count": len(records),
        "work_family_count": EXPECTED_TRAIN_WORK_FAMILY_COUNT,
        "fold_count": FOLD_COUNT,
        "group_plan_manifest_sha256": PINNED_GROUP_PLAN_SHA256,
        "fold_record_distribution": fold_record_distribution,
        "fold_work_family_distribution": fold_work_family_distribution,
        "source_target_slot_count": source_target_slot_count,
        "specialist_support": specialist_support,
        "feature_adapter_version": FEATURE_ADAPTER_VERSION,
        "feature_vocabulary_count": len(feature_vocabulary),
        "feature_occurrence_count": feature_occurrence_count,
        "target_set_policy": TARGET_SET_POLICY,
        "annotation_parse_scope": ANNOTATION_PARSE_SCOPE,
        "score_feature_scope": SCORE_FEATURE_SCOPE,
        "private_record_manifest_sha256": _canonical_sha256(records),
        "records": records,
        "non_train_annotation_bodies_materialized": False,
        "original_validation_target_access": False,
        "calibration_target_access": False,
        "holdout_target_access": False,
        "event_level_training_authorized": False,
        "model_training_started": False,
        "training_authorized": False,
        "production_authority": False,
        "deterministic_resolver_remains_authoritative": True,
    }


def build_stage2b_summary(data: object) -> dict[str, object]:
    if not isinstance(data, dict) or data.get("schema_version") != MATERIALIZATION_SCHEMA:
        raise Stage2BSpecialistMaterializationError(
            "unsupported Stage 2-B materialization schema"
        )
    if data.get("record_count") != EXPECTED_TRAIN_RECORD_COUNT:
        raise Stage2BSpecialistMaterializationError("Stage 2-B record count mismatch")
    if data.get("work_family_count") != EXPECTED_TRAIN_WORK_FAMILY_COUNT:
        raise Stage2BSpecialistMaterializationError(
            "Stage 2-B work-family count mismatch"
        )
    if data.get("group_plan_manifest_sha256") != PINNED_GROUP_PLAN_SHA256:
        raise Stage2BSpecialistMaterializationError("Stage 2-B group plan mismatch")
    if data.get("target_set_policy") != TARGET_SET_POLICY:
        raise Stage2BSpecialistMaterializationError("Stage 2-B target policy changed")
    if data.get("annotation_parse_scope") != ANNOTATION_PARSE_SCOPE:
        raise Stage2BSpecialistMaterializationError("annotation parse scope changed")
    for field in (
        "non_train_annotation_bodies_materialized",
        "original_validation_target_access",
        "calibration_target_access",
        "holdout_target_access",
        "event_level_training_authorized",
        "model_training_started",
        "training_authorized",
        "production_authority",
    ):
        if data.get(field) is not False:
            raise Stage2BSpecialistMaterializationError(
                f"Stage 2-B authority/access boundary violated: {field}"
            )
    if data.get("deterministic_resolver_remains_authoritative") is not True:
        raise Stage2BSpecialistMaterializationError(
            "deterministic resolver authority changed"
        )
    fields = (
        "source_corpus",
        "source_revision",
        "validated_human_decisions_sha256",
        "archive_sha256",
        "score_inventory_sha256",
        "score_inventory_member_count",
        "eligible_original_partition",
        "record_count",
        "work_family_count",
        "fold_count",
        "group_plan_manifest_sha256",
        "fold_record_distribution",
        "fold_work_family_distribution",
        "source_target_slot_count",
        "specialist_support",
        "feature_adapter_version",
        "feature_vocabulary_count",
        "feature_occurrence_count",
        "target_set_policy",
        "annotation_parse_scope",
        "score_feature_scope",
        "private_record_manifest_sha256",
        "non_train_annotation_bodies_materialized",
        "original_validation_target_access",
        "calibration_target_access",
        "holdout_target_access",
        "event_level_training_authorized",
        "model_training_started",
        "training_authorized",
        "production_authority",
        "deterministic_resolver_remains_authoritative",
    )
    summary: dict[str, object] = {"schema_version": SUMMARY_SCHEMA}
    summary.update({field: data[field] for field in fields})
    summary["private_payload_external_only"] = True
    return summary


def materialize_stage2b_specialist_train_from_files(
    decisions_path: str | Path,
    archive_path: str | Path,
) -> dict[str, object]:
    decision_file = _bounded_regular_file(
        decisions_path, max_bytes=MAX_DECISION_BYTES, label="validated decisions"
    )
    if decision_file.is_symlink():
        raise Stage2BSpecialistMaterializationError("decision symlink rejected")
    meta = decision_file.stat()
    if not stat.S_ISREG(meta.st_mode):
        raise Stage2BSpecialistMaterializationError("decision input must be regular file")
    raw = decision_file.read_bytes()
    if len(raw) > MAX_DECISION_BYTES:
        raise Stage2BSpecialistMaterializationError("decision input exceeds size bound")
    data = load_bounded_json(decision_file, max_bytes=MAX_DECISION_BYTES)
    reviewed_split = build_tavern_reviewed_split_from_file(decision_file)
    return build_stage2b_specialist_materialization(
        data,
        decision_artifact_sha256=hashlib.sha256(raw).hexdigest(),
        archive_path=archive_path,
        reviewed_split=reviewed_split,
    )


def canonical_stage2b_json(data: dict[str, object]) -> str:
    if data.get("schema_version") not in {MATERIALIZATION_SCHEMA, SUMMARY_SCHEMA}:
        raise Stage2BSpecialistMaterializationError("unsupported Stage 2-B schema")
    return json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ) + "\n"
