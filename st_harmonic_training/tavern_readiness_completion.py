from __future__ import annotations

import json
from typing import Any

from .normalization import NORMALIZATION_VERSION
from .tavern_gold_materialization import PINNED_VALIDATED_SHA256
from .tavern_normalization_adapter import (
    ADAPTER_VERSION,
    EXPECTED_SELECTED_LABEL_COUNT,
    SUMMARY_SCHEMA as NORMALIZATION_SUMMARY_SCHEMA,
)
from .tavern_raw_label_realization import (
    PINNED_TAVERN_ARCHIVE_SHA256,
    SUMMARY_SCHEMA as REALIZATION_SUMMARY_SCHEMA,
)
from .tavern_readiness_audit import READINESS_SCHEMA
from .tavern_reviewed_split import EXPECTED_RECORD_DISTRIBUTION, EXPECTED_SEED
from .tavern_structure import PINNED_TAVERN_REVISION

COMPLETION_SCHEMA = "st-tavern-dataset-readiness-completion-v1"
EXPECTED_RECORD_COUNT = 694
EXPECTED_GOLD_COUNTS = {"GOLD_EXPERT": 641, "GOLD_VARIANT": 53}
EXPECTED_SELECTED_SOURCE_COUNTS = {"A": 55, "B": 692}
PINNED_REALIZATION_MANIFEST_SHA256 = (
    "39b3cb4f8071605c640621bec20ed9f257f31f638fc6cf717ff9d41ff74bdad3"
)
PINNED_NORMALIZED_TARGET_MANIFEST_SHA256 = (
    "195ec1ce2193f8560043a94f3ea99c8db69b830fff6e60313c88565714450a4c"
)
EXPECTED_STAGE0U_BLOCKERS = [
    "RAW_LABEL_REALIZATION_PENDING",
    "DETERMINISTIC_NORMALIZATION_PENDING",
]


class TavernReadinessCompletionError(ValueError):
    pass


def _require_dict(data: object, schema: str, label: str) -> dict[str, Any]:
    if not isinstance(data, dict) or data.get("schema_version") != schema:
        raise TavernReadinessCompletionError(f"unsupported {label} schema")
    return data


def build_tavern_dataset_readiness_completion(
    stage0u_audit: object,
    realization_summary: object,
    normalization_summary: object,
) -> dict[str, object]:
    audit = _require_dict(stage0u_audit, READINESS_SCHEMA, "Stage 0-U readiness")
    realization = _require_dict(
        realization_summary, REALIZATION_SUMMARY_SCHEMA, "Stage 0-V realization"
    )
    normalization = _require_dict(
        normalization_summary,
        NORMALIZATION_SUMMARY_SCHEMA,
        "Stage 0-W normalization",
    )

    if audit.get("source_corpus") != "TAVERN_REVIEWED_694":
        raise TavernReadinessCompletionError("Stage 0-U source subset mismatch")
    if audit.get("source_revision") != PINNED_TAVERN_REVISION:
        raise TavernReadinessCompletionError("Stage 0-U revision mismatch")
    if audit.get("validated_human_decisions_sha256") != PINNED_VALIDATED_SHA256:
        raise TavernReadinessCompletionError("Stage 0-U human-decision digest mismatch")
    if audit.get("eligible_record_count") != EXPECTED_RECORD_COUNT:
        raise TavernReadinessCompletionError("Stage 0-U eligible record count mismatch")
    if audit.get("gold_tier_counts") != EXPECTED_GOLD_COUNTS:
        raise TavernReadinessCompletionError("Stage 0-U gold distribution mismatch")
    if audit.get("split_seed") != EXPECTED_SEED:
        raise TavernReadinessCompletionError("Stage 0-U split seed mismatch")
    if audit.get("split_distribution") != EXPECTED_RECORD_DISTRIBUTION:
        raise TavernReadinessCompletionError("Stage 0-U split distribution mismatch")
    if audit.get("leakage_gate") != "PASS":
        raise TavernReadinessCompletionError("Stage 0-U leakage gate is not PASS")
    if audit.get("gate_status") != "HOLD" or audit.get("training_authorized") is not False:
        raise TavernReadinessCompletionError("expected the frozen Stage 0-U HOLD state")
    if audit.get("blockers") != EXPECTED_STAGE0U_BLOCKERS:
        raise TavernReadinessCompletionError("Stage 0-U blocker set changed")
    if audit.get("raw_label_realization_complete") is not False:
        raise TavernReadinessCompletionError("Stage 0-U raw-label state changed")
    if audit.get("normalization_complete") is not False:
        raise TavernReadinessCompletionError("Stage 0-U normalization state changed")

    if realization.get("source_corpus") != "TAVERN_REVIEWED_694":
        raise TavernReadinessCompletionError("Stage 0-V source subset mismatch")
    if realization.get("source_revision") != PINNED_TAVERN_REVISION:
        raise TavernReadinessCompletionError("Stage 0-V revision mismatch")
    if realization.get("archive_sha256") != PINNED_TAVERN_ARCHIVE_SHA256:
        raise TavernReadinessCompletionError("Stage 0-V archive digest mismatch")
    if realization.get("validated_human_decisions_sha256") != PINNED_VALIDATED_SHA256:
        raise TavernReadinessCompletionError("Stage 0-V human-decision digest mismatch")
    if realization.get("record_count") != EXPECTED_RECORD_COUNT:
        raise TavernReadinessCompletionError("Stage 0-V record count mismatch")
    if realization.get("selected_label_count") != EXPECTED_SELECTED_LABEL_COUNT:
        raise TavernReadinessCompletionError("Stage 0-V selected-label count mismatch")
    if realization.get("selected_source_counts") != EXPECTED_SELECTED_SOURCE_COUNTS:
        raise TavernReadinessCompletionError("Stage 0-V selected-source distribution mismatch")
    if realization.get("realization_manifest_sha256") != PINNED_REALIZATION_MANIFEST_SHA256:
        raise TavernReadinessCompletionError("Stage 0-V realization manifest mismatch")
    if realization.get("raw_label_realization_complete") is not True:
        raise TavernReadinessCompletionError("Stage 0-V raw-label realization incomplete")
    if realization.get("normalization_complete") is not False:
        raise TavernReadinessCompletionError("Stage 0-V unexpectedly claims normalization")
    if realization.get("training_authorized") is not False:
        raise TavernReadinessCompletionError("Stage 0-V cannot authorize training")

    if normalization.get("source_corpus") != "TAVERN_REVIEWED_694":
        raise TavernReadinessCompletionError("Stage 0-W source subset mismatch")
    if normalization.get("source_revision") != PINNED_TAVERN_REVISION:
        raise TavernReadinessCompletionError("Stage 0-W revision mismatch")
    if normalization.get("archive_sha256") != realization.get("archive_sha256"):
        raise TavernReadinessCompletionError("Stage 0-V/W archive digest disagreement")
    if normalization.get("validated_human_decisions_sha256") != realization.get(
        "validated_human_decisions_sha256"
    ):
        raise TavernReadinessCompletionError("Stage 0-V/W human-decision digest disagreement")
    if normalization.get("record_count") != EXPECTED_RECORD_COUNT:
        raise TavernReadinessCompletionError("Stage 0-W record count mismatch")
    if normalization.get("normalized_target_count") != EXPECTED_SELECTED_LABEL_COUNT:
        raise TavernReadinessCompletionError("Stage 0-W target count mismatch")
    if normalization.get("adapter_version") != ADAPTER_VERSION:
        raise TavernReadinessCompletionError("Stage 0-W adapter version mismatch")
    if normalization.get("normalization_version") != NORMALIZATION_VERSION:
        raise TavernReadinessCompletionError("Stage 0-W normalization version mismatch")
    if normalization.get("normalized_target_manifest_sha256") != PINNED_NORMALIZED_TARGET_MANIFEST_SHA256:
        raise TavernReadinessCompletionError("Stage 0-W normalized-target manifest mismatch")
    if normalization.get("raw_label_realization_complete") is not True:
        raise TavernReadinessCompletionError("Stage 0-W lost raw-label realization")
    if normalization.get("normalization_complete") is not True:
        raise TavernReadinessCompletionError("Stage 0-W normalization incomplete")
    if normalization.get("partition_assignment_authorized") is not False:
        raise TavernReadinessCompletionError("Stage 0-W must not reassign partitions")
    if normalization.get("training_authorized") is not False:
        raise TavernReadinessCompletionError("Stage 0-W cannot authorize training")

    return {
        "schema_version": COMPLETION_SCHEMA,
        "source_corpus": "TAVERN_REVIEWED_694",
        "source_revision": PINNED_TAVERN_REVISION,
        "archive_sha256": PINNED_TAVERN_ARCHIVE_SHA256,
        "validated_human_decisions_sha256": PINNED_VALIDATED_SHA256,
        "record_count": EXPECTED_RECORD_COUNT,
        "gold_tier_counts": EXPECTED_GOLD_COUNTS,
        "normalized_target_count": EXPECTED_SELECTED_LABEL_COUNT,
        "split_seed": EXPECTED_SEED,
        "split_distribution": EXPECTED_RECORD_DISTRIBUTION,
        "leakage_gate": "PASS",
        "realization_manifest_sha256": PINNED_REALIZATION_MANIFEST_SHA256,
        "normalized_target_manifest_sha256": PINNED_NORMALIZED_TARGET_MANIFEST_SHA256,
        "raw_label_realization_complete": True,
        "normalization_complete": True,
        "resolved_stage0u_blockers": EXPECTED_STAGE0U_BLOCKERS,
        "remaining_dataset_blockers": [],
        "dataset_readiness_gate": "PASS",
        "training_payload_ready": True,
        "next_required_gate": "PROMOTION_THRESHOLDS_PENDING_BASELINE",
        "model_training_started": False,
        "model_training_authorized": False,
        "training_authorized": False,
    }


def canonical_tavern_dataset_readiness_completion_json(
    data: dict[str, object],
) -> str:
    if data.get("schema_version") != COMPLETION_SCHEMA:
        raise TavernReadinessCompletionError("unsupported readiness completion schema")
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
