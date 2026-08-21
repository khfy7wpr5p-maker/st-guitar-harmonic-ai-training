from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

from .safe_ingest import inspect_zip

PINNED_TAVERN_REVISION = "7cc65dc5365603a92376af50ac71491bea7a16ae"
DECLARED_WORK_COUNT = 27
DECLARED_PHRASE_COUNT = 1060
DOCUMENTED_ANNOTATORS = {"A", "B"}
STRUCTURE_SCHEMA = "st-tavern-structure-v1"

SCORE_RE = re.compile(r"_V?(\d{2})_(\d{2})_score\.krn$")
ANALYSIS_RE = re.compile(r"_V?(\d{2})_(\d{2})_encoder([A-Za-z])\.krn$")
JOINED_RE = re.compile(r"_V?(\d{2})_(\d{2})[a-z]*_([A-Za-z])\.krn$")


class TavernStructureError(ValueError):
    pass


@dataclass(frozen=True)
class PhraseArtifacts:
    score: str | None
    analyses: tuple[tuple[str, str], ...]
    joined: tuple[tuple[str, str], ...]

    def analysis_map(self) -> dict[str, str]:
        return dict(self.analyses)

    def joined_map(self) -> dict[str, str]:
        return dict(self.joined)


def _archive_root(infos: tuple[zipfile.ZipInfo, ...]) -> str:
    roots: set[str] = set()
    for info in infos:
        parts = PurePosixPath(info.filename.replace("\\", "/")).parts
        if parts:
            roots.add(parts[0])
    if len(roots) != 1:
        raise TavernStructureError("TAVERN archive must have exactly one top-level root")
    root = next(iter(roots))
    if not root.startswith("TAVERN-"):
        raise TavernStructureError(f"unexpected TAVERN archive root: {root}")
    return root


def _logical_path(name: str, root: str) -> str:
    path = PurePosixPath(name.replace("\\", "/"))
    if not path.parts or path.parts[0] != root:
        raise TavernStructureError(f"member outside TAVERN root: {name}")
    if len(path.parts) == 1:
        return ""
    return PurePosixPath(*path.parts[1:]).as_posix()


def _phrase_key(work_id: str, variation: str, phrase: str) -> str:
    return f"{work_id}:{variation}:{phrase}"


def _status(artifacts: PhraseArtifacts) -> str:
    analyses = artifacts.analysis_map()
    has_score = artifacts.score is not None
    has_a = "A" in analyses
    has_b = "B" in analyses
    if has_score and has_a and has_b:
        return "PAIR_COMPLETE"
    if has_score and has_a and not has_b:
        return "SCORE_A_ONLY"
    if has_score and has_b and not has_a:
        return "SCORE_B_ONLY"
    if has_score and not has_a and not has_b:
        return "SCORE_ONLY"
    if not has_score and (has_a or has_b):
        return "ANALYSIS_WITHOUT_SCORE"
    return "DERIVED_OR_UNDOCUMENTED_ONLY"


def _set_once(
    mapping: dict[str, str],
    key: str,
    value: str,
    *,
    role: str,
) -> None:
    if key in mapping:
        raise TavernStructureError(f"duplicate {role} for phrase {key}")
    mapping[key] = value


def build_tavern_structure_audit(
    archive_path: str | Path,
    *,
    immutable_revision: str,
) -> dict[str, object]:
    revision = immutable_revision.strip()
    if revision != PINNED_TAVERN_REVISION:
        raise TavernStructureError(
            "TAVERN structure adapter is pinned to "
            f"{PINNED_TAVERN_REVISION}; got {revision or '<empty>'}"
        )

    archive = Path(archive_path)
    infos = inspect_zip(archive)
    root = _archive_root(infos)
    files = [info for info in infos if not info.is_dir()]
    logical_names = {_logical_path(info.filename, root) for info in files}
    for required in ("README.md", "LICENSE"):
        if required not in logical_names:
            raise TavernStructureError(f"required TAVERN source file missing: {required}")

    score_by_phrase: dict[str, str] = {}
    analysis_by_phrase: dict[str, dict[str, str]] = defaultdict(dict)
    joined_by_phrase: dict[str, dict[str, str]] = defaultdict(dict)
    phrase_work: dict[str, str] = {}
    works_seen: set[str] = set()
    support_score_krn: list[str] = []
    undocumented_analysis: Counter[str] = Counter()

    for info in sorted(files, key=lambda item: _logical_path(item.filename, root)):
        logical = _logical_path(info.filename, root)
        parts = PurePosixPath(logical).parts
        if len(parts) < 3 or parts[0] not in {"Beethoven", "Mozart"}:
            continue

        work_id = f"{parts[0]}/{parts[1]}"
        works_seen.add(work_id)
        filename = parts[-1]

        if parts[2] == "Krn" and filename.endswith(".krn"):
            match = SCORE_RE.search(filename)
            if not match:
                support_score_krn.append(logical)
                continue
            key = _phrase_key(work_id, match.group(1), match.group(2))
            _set_once(score_by_phrase, key, logical, role="score")
            phrase_work[key] = work_id
            continue

        if (
            len(parts) >= 5
            and parts[2] == "Encodings"
            and parts[3].startswith("Encoder_")
            and filename.endswith(".krn")
        ):
            match = ANALYSIS_RE.search(filename)
            if not match:
                raise TavernStructureError(f"unparseable primary analysis filename: {logical}")
            annotator = match.group(3).upper()
            directory_annotator = parts[3].removeprefix("Encoder_").upper()
            if directory_annotator != annotator:
                raise TavernStructureError(
                    f"analysis annotator path/filename mismatch: {logical}"
                )
            key = _phrase_key(work_id, match.group(1), match.group(2))
            _set_once(
                analysis_by_phrase[key],
                annotator,
                logical,
                role=f"analysis:{annotator}",
            )
            phrase_work[key] = work_id
            if annotator not in DOCUMENTED_ANNOTATORS:
                undocumented_analysis[annotator] += 1
            continue

        if parts[2] == "Joined" and filename.endswith(".krn"):
            match = JOINED_RE.search(filename)
            if not match:
                raise TavernStructureError(f"unparseable joined filename: {logical}")
            annotator = match.group(3).upper()
            if annotator not in DOCUMENTED_ANNOTATORS:
                raise TavernStructureError(
                    f"undocumented joined annotator {annotator}: {logical}"
                )
            key = _phrase_key(work_id, match.group(1), match.group(2))
            _set_once(
                joined_by_phrase[key],
                annotator,
                logical,
                role=f"joined:{annotator}",
            )
            phrase_work[key] = work_id

    phrase_keys = sorted(
        set(score_by_phrase) | set(analysis_by_phrase) | set(joined_by_phrase)
    )
    work_status_counts: dict[str, Counter[str]] = defaultdict(Counter)
    work_artifact_counts: dict[str, Counter[str]] = defaultdict(Counter)
    overall_status: Counter[str] = Counter()
    joined_ab_count = 0

    for key in phrase_keys:
        analyses = analysis_by_phrase.get(key, {})
        joined = joined_by_phrase.get(key, {})
        artifacts = PhraseArtifacts(
            score=score_by_phrase.get(key),
            analyses=tuple(sorted(analyses.items())),
            joined=tuple(sorted(joined.items())),
        )
        status = _status(artifacts)
        overall_status[status] += 1
        work_id = phrase_work[key]
        work_status_counts[work_id][status] += 1

        if artifacts.score is not None:
            work_artifact_counts[work_id]["score"] += 1
        for annotator in analyses:
            work_artifact_counts[work_id][f"analysis_{annotator}"] += 1
        for annotator in joined:
            work_artifact_counts[work_id][f"joined_{annotator}"] += 1
        if set(joined) == DOCUMENTED_ANNOTATORS:
            joined_ab_count += 1

    blockers: list[str] = []
    if len(works_seen) != DECLARED_WORK_COUNT:
        blockers.append(
            f"DECLARED_OBSERVED_WORK_COUNT_MISMATCH:{DECLARED_WORK_COUNT}:{len(works_seen)}"
        )
    if len(phrase_keys) != DECLARED_PHRASE_COUNT:
        blockers.append(
            f"DECLARED_OBSERVED_PHRASE_COUNT_MISMATCH:"
            f"{DECLARED_PHRASE_COUNT}:{len(phrase_keys)}"
        )
    for annotator, count in sorted(undocumented_analysis.items()):
        blockers.append(f"UNDOCUMENTED_PRIMARY_ANNOTATOR:{annotator}:{count}")

    incomplete = len(phrase_keys) - overall_status["PAIR_COMPLETE"]
    if incomplete:
        blockers.append(f"INCOMPLETE_PRIMARY_PAIR_COVERAGE:{incomplete}")
    if overall_status["ANALYSIS_WITHOUT_SCORE"]:
        blockers.append(
            f"PRIMARY_ANALYSIS_WITHOUT_SCORE:"
            f"{overall_status['ANALYSIS_WITHOUT_SCORE']}"
        )
    if overall_status["SCORE_ONLY"]:
        blockers.append(f"SCORE_WITHOUT_PRIMARY_ANALYSIS:{overall_status['SCORE_ONLY']}")
    if overall_status["DERIVED_OR_UNDOCUMENTED_ONLY"]:
        blockers.append(
            f"DERIVED_OR_UNDOCUMENTED_ONLY:"
            f"{overall_status['DERIVED_OR_UNDOCUMENTED_ONLY']}"
        )
    blockers.append("CROSS_CORPUS_DEDUP_REQUIRED_BEFORE_FINAL_SPLIT")

    work_summaries = []
    for work_id in sorted(works_seen):
        artifact_counts = work_artifact_counts[work_id]
        status_counts = work_status_counts[work_id]
        work_summaries.append(
            {
                "source_work_id": work_id,
                "work_family_candidate_id": f"TAVERN::{work_id}",
                "canonical_work_id": None,
                "split_group_id": None,
                "partition": "QUARANTINE",
                "artifact_counts": {
                    key: artifact_counts[key] for key in sorted(artifact_counts)
                },
                "phrase_status_counts": {
                    key: status_counts[key] for key in sorted(status_counts)
                },
            }
        )

    return {
        "schema_version": STRUCTURE_SCHEMA,
        "source_corpus": "TAVERN",
        "immutable_revision": revision,
        "declared_counts": {
            "works": DECLARED_WORK_COUNT,
            "phrases": DECLARED_PHRASE_COUNT,
        },
        "observed_counts": {
            "works": len(works_seen),
            "phrase_keys": len(phrase_keys),
            "score_phrase_files": len(score_by_phrase),
            "analysis_A_files": sum(
                1 for values in analysis_by_phrase.values() if "A" in values
            ),
            "analysis_B_files": sum(
                1 for values in analysis_by_phrase.values() if "B" in values
            ),
            "analysis_undocumented_files": sum(undocumented_analysis.values()),
            "joined_AB_phrase_keys": joined_ab_count,
            "support_score_krn_files": len(support_score_krn),
        },
        "phrase_status_counts": {
            key: overall_status[key] for key in sorted(overall_status)
        },
        "documented_primary_annotators": sorted(DOCUMENTED_ANNOTATORS),
        "undocumented_primary_annotators": {
            key: undocumented_analysis[key] for key in sorted(undocumented_analysis)
        },
        "work_summaries": work_summaries,
        "blockers": sorted(set(blockers)),
        "admission_status": "HOLD",
        "training_authorized": False,
    }


def canonical_structure_json(audit: dict[str, object]) -> str:
    if audit.get("schema_version") != STRUCTURE_SCHEMA:
        raise TavernStructureError("unsupported TAVERN structure schema")
    return json.dumps(
        audit,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ) + "\n"
