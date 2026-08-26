from __future__ import annotations

from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import statistics
from typing import Any

from .safe_ingest import load_bounded_json
from .stage1e_internal_cv import FOLD_COUNT, PINNED_GROUP_PLAN_SHA256
from .stage2c_contract import (
    PINNED_STAGE2B_PRIVATE_RECORD_MANIFEST_SHA256,
    PINNED_STAGE2B_RECORD_COUNT,
    PINNED_STAGE2B_WORK_FAMILY_COUNT,
    SPECIALIST_IDS,
)
from .stage2c_specialist_cv import validate_stage2b_private_payload

SUMMARY_SCHEMA = "st-stage2d-target-learnability-summary-v1"
AUDIT_SCOPE = "STAGE0_T_TRAIN_TARGETS_ONLY"
RESULT_SCOPE = "TRAIN_ONLY_TARGET_LEARNABILITY_DIAGNOSTIC"
MAX_PRIVATE_INPUT_BYTES = 64 * 1024 * 1024
SEQUENCE_SPECIALISTS = {
    "ROMAN_NUMERAL_SPECIALIST",
    "FUNCTION_SPECIALIST",
}


class Stage2DTargetLearnabilityError(ValueError):
    pass


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 12)


def _nearest_rank(values: list[int], fraction: float) -> int:
    if not values:
        raise Stage2DTargetLearnabilityError("cannot summarize empty sequence lengths")
    ordered = sorted(values)
    rank = max(1, math.ceil(fraction * len(ordered)))
    return ordered[rank - 1]


def _sequence_length(specialist_id: str, target: str) -> int:
    if specialist_id not in SPECIALIST_IDS:
        raise Stage2DTargetLearnabilityError("unsupported specialist")
    if specialist_id not in SEQUENCE_SPECIALISTS:
        return 1
    try:
        value = json.loads(target)
    except json.JSONDecodeError as exc:
        raise Stage2DTargetLearnabilityError(
            f"{specialist_id} target is not canonical JSON sequence text"
        ) from exc
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item for item in value)
    ):
        raise Stage2DTargetLearnabilityError(
            f"{specialist_id} target sequence is malformed"
        )
    return len(value)


def _length_summary(lengths: list[int]) -> dict[str, object]:
    if not lengths:
        return {
            "target_occurrence_count": 0,
            "min": None,
            "max": None,
            "mean": None,
            "median": None,
            "p90_nearest_rank": None,
        }
    return {
        "target_occurrence_count": len(lengths),
        "min": min(lengths),
        "max": max(lengths),
        "mean": round(statistics.fmean(lengths), 12),
        "median": round(float(statistics.median(lengths)), 12),
        "p90_nearest_rank": _nearest_rank(lengths, 0.90),
    }


def _audit_specialist(
    records: list[dict[str, Any]], specialist_id: str
) -> dict[str, object]:
    if specialist_id not in SPECIALIST_IDS:
        raise Stage2DTargetLearnabilityError("unsupported specialist")

    eligible = [row for row in records if row["target_sets"][specialist_id]]
    if not eligible:
        raise Stage2DTargetLearnabilityError("specialist has no eligible TRAIN records")

    target_record_counts: Counter[str] = Counter()
    target_fold_presence: defaultdict[str, set[int]] = defaultdict(set)
    sequence_lengths: list[int] = []
    multi_target_records = 0
    for row in eligible:
        targets = row["target_sets"][specialist_id]
        if len(targets) > 1:
            multi_target_records += 1
        fold = int(row["development_fold"])
        for target in targets:
            target_record_counts[target] += 1
            target_fold_presence[target].add(fold)
            sequence_lengths.append(_sequence_length(specialist_id, target))

    unique_target_count = len(target_record_counts)
    target_occurrence_count = sum(target_record_counts.values())
    singleton_target_count = sum(
        1 for count in target_record_counts.values() if count == 1
    )
    fold_presence_distribution = {
        str(fold_count): sum(
            1
            for folds in target_fold_presence.values()
            if len(folds) == fold_count
        )
        for fold_count in range(1, FOLD_COUNT + 1)
    }

    folds: dict[str, object] = {}
    pooled_evaluation_records = 0
    pooled_target_occurrences = 0
    pooled_unseen_target_occurrences = 0
    pooled_records_without_seen_target = 0
    pooled_records_with_any_unseen = 0

    for eval_fold in range(FOLD_COUNT):
        fit = [
            row
            for row in eligible
            if int(row["development_fold"]) != eval_fold
        ]
        evaluation = [
            row
            for row in eligible
            if int(row["development_fold"]) == eval_fold
        ]
        if not fit or not evaluation:
            raise Stage2DTargetLearnabilityError("empty fit/evaluation fold")

        fit_groups = {str(row["split_group_id"]) for row in fit}
        evaluation_groups = {str(row["split_group_id"]) for row in evaluation}
        if fit_groups & evaluation_groups:
            raise Stage2DTargetLearnabilityError(
                "work-family leakage detected during learnability audit"
            )

        fit_targets = {
            target
            for row in fit
            for target in row["target_sets"][specialist_id]
        }
        evaluation_targets = {
            target
            for row in evaluation
            for target in row["target_sets"][specialist_id]
        }
        evaluation_target_occurrences = sum(
            len(row["target_sets"][specialist_id]) for row in evaluation
        )
        unseen_target_occurrences = sum(
            1
            for row in evaluation
            for target in row["target_sets"][specialist_id]
            if target not in fit_targets
        )
        records_without_seen_target = sum(
            1
            for row in evaluation
            if not any(
                target in fit_targets
                for target in row["target_sets"][specialist_id]
            )
        )
        records_with_any_unseen = sum(
            1
            for row in evaluation
            if any(
                target not in fit_targets
                for target in row["target_sets"][specialist_id]
            )
        )
        evaluation_count = len(evaluation)

        folds[str(eval_fold)] = {
            "fit_record_count": len(fit),
            "evaluation_record_count": evaluation_count,
            "fit_work_family_count": len(fit_groups),
            "evaluation_work_family_count": len(evaluation_groups),
            "fit_unique_target_count": len(fit_targets),
            "evaluation_unique_target_count": len(evaluation_targets),
            "shared_unique_target_count": len(fit_targets & evaluation_targets),
            "evaluation_target_occurrence_count": evaluation_target_occurrences,
            "unseen_target_occurrence_count": unseen_target_occurrences,
            "unseen_target_occurrence_rate": _ratio(
                unseen_target_occurrences, evaluation_target_occurrences
            ),
            "records_with_any_unseen_target": records_with_any_unseen,
            "records_with_no_seen_acceptable_target": records_without_seen_target,
            "closed_set_oracle_ceiling": _ratio(
                evaluation_count - records_without_seen_target, evaluation_count
            ),
        }

        pooled_evaluation_records += evaluation_count
        pooled_target_occurrences += evaluation_target_occurrences
        pooled_unseen_target_occurrences += unseen_target_occurrences
        pooled_records_without_seen_target += records_without_seen_target
        pooled_records_with_any_unseen += records_with_any_unseen

    if pooled_evaluation_records != len(eligible):
        raise Stage2DTargetLearnabilityError(
            "pooled fold evaluation count differs from eligible TRAIN records"
        )

    return {
        "eligible_record_count": len(eligible),
        "missing_record_count": PINNED_STAGE2B_RECORD_COUNT - len(eligible),
        "target_occurrence_count": target_occurrence_count,
        "unique_target_count": unique_target_count,
        "unique_target_per_record_ratio": _ratio(unique_target_count, len(eligible)),
        "target_reuse_factor": round(
            target_occurrence_count / unique_target_count, 12
        ),
        "singleton_target_count": singleton_target_count,
        "singleton_target_fraction": _ratio(
            singleton_target_count, unique_target_count
        ),
        "multi_target_record_count": multi_target_records,
        "target_fold_presence_distribution": fold_presence_distribution,
        "sequence_length": _length_summary(sequence_lengths),
        "folds": folds,
        "pooled": {
            "evaluation_record_count": pooled_evaluation_records,
            "evaluation_target_occurrence_count": pooled_target_occurrences,
            "unseen_target_occurrence_count": pooled_unseen_target_occurrences,
            "unseen_target_occurrence_rate": _ratio(
                pooled_unseen_target_occurrences, pooled_target_occurrences
            ),
            "records_with_any_unseen_target": pooled_records_with_any_unseen,
            "records_with_no_seen_acceptable_target": pooled_records_without_seen_target,
            "closed_set_oracle_ceiling": _ratio(
                pooled_evaluation_records - pooled_records_without_seen_target,
                pooled_evaluation_records,
            ),
        },
    }


def build_stage2d_target_learnability_summary(
    private_payload: object,
) -> dict[str, object]:
    try:
        records = validate_stage2b_private_payload(private_payload)
    except Exception as exc:
        if isinstance(exc, Stage2DTargetLearnabilityError):
            raise
        raise Stage2DTargetLearnabilityError(
            "Stage 2-B private payload failed pinned validation"
        ) from exc

    specialists = {
        specialist_id: _audit_specialist(records, specialist_id)
        for specialist_id in SPECIALIST_IDS
    }
    return {
        "schema_version": SUMMARY_SCHEMA,
        "source_stage2b_private_record_manifest_sha256": (
            PINNED_STAGE2B_PRIVATE_RECORD_MANIFEST_SHA256
        ),
        "record_count": PINNED_STAGE2B_RECORD_COUNT,
        "work_family_count": PINNED_STAGE2B_WORK_FAMILY_COUNT,
        "fold_count": FOLD_COUNT,
        "group_plan_manifest_sha256": PINNED_GROUP_PLAN_SHA256,
        "audit_scope": AUDIT_SCOPE,
        "result_scope": RESULT_SCOPE,
        "specialists": specialists,
        "target_values_serialized": False,
        "model_fitting_started": False,
        "model_selection_started": False,
        "full_train_final_fit_started": False,
        "original_validation_target_access": False,
        "calibration_target_access": False,
        "holdout_target_access": False,
        "event_level_training_authorized": False,
        "production_authority": False,
        "deterministic_resolver_remains_authoritative": True,
    }


def validate_stage2d_summary(data: object) -> dict[str, Any]:
    if not isinstance(data, dict) or data.get("schema_version") != SUMMARY_SCHEMA:
        raise Stage2DTargetLearnabilityError("unsupported Stage 2-D summary schema")
    expected = {
        "source_stage2b_private_record_manifest_sha256": (
            PINNED_STAGE2B_PRIVATE_RECORD_MANIFEST_SHA256
        ),
        "record_count": PINNED_STAGE2B_RECORD_COUNT,
        "work_family_count": PINNED_STAGE2B_WORK_FAMILY_COUNT,
        "fold_count": FOLD_COUNT,
        "group_plan_manifest_sha256": PINNED_GROUP_PLAN_SHA256,
        "audit_scope": AUDIT_SCOPE,
        "result_scope": RESULT_SCOPE,
        "target_values_serialized": False,
        "model_fitting_started": False,
        "model_selection_started": False,
        "full_train_final_fit_started": False,
        "original_validation_target_access": False,
        "calibration_target_access": False,
        "holdout_target_access": False,
        "event_level_training_authorized": False,
        "production_authority": False,
        "deterministic_resolver_remains_authoritative": True,
    }
    for field, value in expected.items():
        if data.get(field) != value:
            raise Stage2DTargetLearnabilityError(
                f"Stage 2-D summary boundary changed: {field}"
            )
    specialists = data.get("specialists")
    if not isinstance(specialists, dict) or set(specialists) != set(SPECIALIST_IDS):
        raise Stage2DTargetLearnabilityError("Stage 2-D specialist set changed")
    return data


def run_stage2d_target_learnability_from_file(
    private_payload_path: str | Path,
) -> dict[str, object]:
    path = Path(private_payload_path).expanduser().resolve()
    data = load_bounded_json(path, max_bytes=MAX_PRIVATE_INPUT_BYTES)
    summary = build_stage2d_target_learnability_summary(data)
    validate_stage2d_summary(summary)
    return summary


def canonical_stage2d_json(data: dict[str, object]) -> str:
    validate_stage2d_summary(data)
    return json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ) + "\n"
