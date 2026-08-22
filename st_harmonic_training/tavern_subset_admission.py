from __future__ import annotations

import json
from typing import Any

from .contracts import SourceManifest
from .normalization import NORMALIZATION_VERSION
from .tavern_gold_materialization import SUMMARY_SCHEMA, PINNED_VALIDATED_SHA256
from .tavern_structure import PINNED_TAVERN_REVISION

ADMISSION_SCHEMA = "st-tavern-reviewed-subset-admission-v1"
SUBSET_CORPUS = "TAVERN_REVIEWED_694"
RAW_ARCHIVE_SHA256 = "b95d85bb3f1e5c0f4ea6df772928d247243485abd93153f0550d6be2fba4fc63"
SCORE_SHA256 = "7bdb7737e2f215bf1cda48e985279478d0b16751bbcca40c165179c5c85a5f7a"
ANALYSIS_SHA256 = "04c327ed97774729f208b8767bd020e6106809a511576b08e853b8095a82907d"
EXPECTED_RECORD_COUNT = 694
EXPECTED_EXCLUDED_COUNT = 243


class TavernSubsetAdmissionError(ValueError):
    pass


def build_tavern_reviewed_subset_admission(materialization_summary: object) -> dict[str, object]:
    if not isinstance(materialization_summary, dict) or materialization_summary.get("schema_version") != SUMMARY_SCHEMA:
        raise TavernSubsetAdmissionError("unsupported Stage 0-Q materialization summary")
    if materialization_summary.get("source_corpus") != "TAVERN":
        raise TavernSubsetAdmissionError("source corpus mismatch")
    if materialization_summary.get("source_revision") != PINNED_TAVERN_REVISION:
        raise TavernSubsetAdmissionError("source revision mismatch")
    if materialization_summary.get("validated_human_decisions_sha256") != PINNED_VALIDATED_SHA256:
        raise TavernSubsetAdmissionError("validated human-decision digest mismatch")
    if materialization_summary.get("normalization_version") != NORMALIZATION_VERSION:
        raise TavernSubsetAdmissionError("normalization version mismatch")
    if materialization_summary.get("record_count") != EXPECTED_RECORD_COUNT:
        raise TavernSubsetAdmissionError("reviewed subset record count mismatch")
    if materialization_summary.get("gold_tier_counts") != {"GOLD_EXPERT": 641, "GOLD_VARIANT": 53}:
        raise TavernSubsetAdmissionError("gold tier distribution mismatch")
    if materialization_summary.get("hash_bound_external_label_pending_count") != EXPECTED_RECORD_COUNT:
        raise TavernSubsetAdmissionError("pending external-label count mismatch")
    if materialization_summary.get("gold_assignment_authorized") is not True:
        raise TavernSubsetAdmissionError("Stage 0-Q gold assignment is not authorized")
    if materialization_summary.get("partition_assignment_authorized") is not False:
        raise TavernSubsetAdmissionError("partition authority must remain false")
    if materialization_summary.get("training_authorized") is not False:
        raise TavernSubsetAdmissionError("Stage 0-R cannot accept training authorization")

    manifest_dict: dict[str, Any] = {
        "source_corpus": SUBSET_CORPUS,
        "source_url": "https://github.com/jcdevaney/TAVERN",
        "immutable_revision": PINNED_TAVERN_REVISION,
        "release_tag_commit_doi": f"commit:{PINNED_TAVERN_REVISION}",
        "raw_archive_sha256": RAW_ARCHIVE_SHA256,
        "score_sha256": SCORE_SHA256,
        "analysis_sha256": ANALYSIS_SHA256,
        "license_id": "CC-BY-SA-4.0",
        "license_scope": "Only the hash-bound Stage 0-R reviewed subset; upstream TAVERN corpus licence at the pinned revision",
        "source_provenance": "TAVERN immutable archive with Stage 0-H integrity receipts",
        "annotation_provenance": "Human TAVERN A/B annotations selected or preserved by Stage 0-M human review and Stage 0-Q gold materialization",
        "known_issues": [
            "Selected raw label bytes are still external and must be reread and hash-verified before training",
            "Deterministic TAVERN semantic normalization adapter is not yet materialized",
            "203 PDF-capture-loss and 40 schema-incompatible review records are excluded and remain quarantined",
            "When-in-Rome and AugmentedNet aliases must inherit the same work-family split group before partitioning",
        ],
        "acquisition_status": "READY",
        "quarantine_reason": None,
    }
    manifest = SourceManifest.from_dict(manifest_dict)
    return {
        "schema_version": ADMISSION_SCHEMA,
        "subset_corpus": SUBSET_CORPUS,
        "source_revision": PINNED_TAVERN_REVISION,
        "admitted_record_count": EXPECTED_RECORD_COUNT,
        "excluded_record_count": EXPECTED_EXCLUDED_COUNT,
        "gold_tier_counts": {"GOLD_EXPERT": 641, "GOLD_VARIANT": 53},
        "admission_scope": "DATASET_ENGINEERING_ONLY",
        "source_manifest": manifest_dict,
        "raw_label_realization_complete": False,
        "normalization_complete": False,
        "partition_assignment_authorized": False,
        "training_authorized": False,
    }


def canonical_tavern_subset_admission_json(data: dict[str, object]) -> str:
    if data.get("schema_version") != ADMISSION_SCHEMA:
        raise TavernSubsetAdmissionError("unsupported admission schema")
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
