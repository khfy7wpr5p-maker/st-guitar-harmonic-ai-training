from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

from .safe_ingest import inspect_zip

STRUCTURE_SCHEMA = "st-tavern-structure-v1"
WORK_FAMILY_SCHEMA = "st-tavern-work-families-v1"
DOCUMENTED_PHRASE_COUNT = 1060
DOCUMENTED_ANNOTATORS = ("Encoder_A", "Encoder_B")
DOCUMENTED_WORKS = {
    "Beethoven": (
        "B063", "B064", "B065", "B066", "B068", "B069", "B070", "B071",
        "B072", "B073", "B075", "B076", "B077", "B078", "B080", "Opus34", "Opus76",
    ),
    "Mozart": (
        "K025", "K179", "K265", "K353", "K354", "K398", "K455", "K501", "K573", "K613",
    ),
}
SCORE_RE = re.compile(r"^(?P<phrase>.+)_score\.krn$")
ANALYSIS_RE = re.compile(r"^(?P<phrase>.+)_encoder(?P<suffix>[A-Za-z0-9]+)\.krn$")


class TavernStructureError(ValueError):
    pass


@dataclass(frozen=True)
class PhrasePresence:
    score: bool = False
    annotators: frozenset[str] = frozenset()


@dataclass(frozen=True)
class TavernStructureReport:
    work_counts: dict[str, int]
    observed_unique_phrase_keys: int
    complete_score_a_b: int
    score_a_without_b: int
    score_b_without_a: int
    score_without_documented_analysis: int
    documented_analysis_without_score: int
    undocumented_annotator_file_counts: dict[str, int]
    undocumented_only_phrase_keys: int
    blockers: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": STRUCTURE_SCHEMA,
            "documented_phrase_count": DOCUMENTED_PHRASE_COUNT,
            "documented_annotators": list(DOCUMENTED_ANNOTATORS),
            "work_counts": self.work_counts,
            "observed_unique_phrase_keys": self.observed_unique_phrase_keys,
            "complete_score_a_b": self.complete_score_a_b,
            "score_a_without_b": self.score_a_without_b,
            "score_b_without_a": self.score_b_without_a,
            "score_without_documented_analysis": self.score_without_documented_analysis,
            "documented_analysis_without_score": self.documented_analysis_without_score,
            "undocumented_annotator_file_counts": self.undocumented_annotator_file_counts,
            "undocumented_only_phrase_keys": self.undocumented_only_phrase_keys,
            "blockers": list(self.blockers),
            "blanket_teacher_gold_authorized": False,
            "split_assignment_authorized": False,
        }


def _root_from_names(names: list[str]) -> str:
    roots = {PurePosixPath(name.replace("\\", "/")).parts[0] for name in names if name}
    if len(roots) != 1:
        raise TavernStructureError("TAVERN archive must contain one top-level root")
    root = next(iter(roots))
    if not root.startswith("TAVERN-"):
        raise TavernStructureError(f"unexpected TAVERN archive root: {root}")
    return root


def _logical_path(name: str, root: str) -> str:
    parts = PurePosixPath(name.replace("\\", "/")).parts
    if not parts or parts[0] != root:
        raise TavernStructureError(f"member outside TAVERN root: {name}")
    return PurePosixPath(*parts[1:]).as_posix() if len(parts) > 1 else ""


def _phrase_key(logical: str) -> tuple[str, str | None] | None:
    path = PurePosixPath(logical)
    parts = path.parts
    if len(parts) < 4 or parts[0] not in DOCUMENTED_WORKS:
        return None
    composer, work = parts[0], parts[1]
    if work not in DOCUMENTED_WORKS[composer] or path.suffix.lower() != ".krn":
        return None

    if parts[2] == "Krn":
        match = SCORE_RE.match(path.name)
        if not match:
            return None
        return f"{composer}/{work}/{match.group('phrase')}", "score"

    if len(parts) >= 5 and parts[2] == "Encodings" and parts[3].startswith("Encoder_"):
        match = ANALYSIS_RE.match(path.name)
        if not match:
            return None
        folder_annotator = parts[3]
        suffix_annotator = f"Encoder_{match.group('suffix')}"
        if folder_annotator != suffix_annotator:
            raise TavernStructureError(
                f"analysis annotator folder/suffix mismatch: {logical}"
            )
        return f"{composer}/{work}/{match.group('phrase')}", folder_annotator
    return None


def analyze_logical_paths(logical_paths: list[str]) -> TavernStructureReport:
    works_seen: dict[str, set[str]] = {composer: set() for composer in DOCUMENTED_WORKS}
    score_keys: set[str] = set()
    annotator_keys: dict[str, set[str]] = defaultdict(set)
    annotator_files: Counter[str] = Counter()

    for logical in sorted(set(logical_paths)):
        parts = PurePosixPath(logical).parts
        if len(parts) >= 2 and parts[0] in DOCUMENTED_WORKS and parts[1] in DOCUMENTED_WORKS[parts[0]]:
            works_seen[parts[0]].add(parts[1])
        parsed = _phrase_key(logical)
        if parsed is None:
            continue
        key, role = parsed
        if role == "score":
            score_keys.add(key)
        else:
            assert role is not None
            annotator_keys[role].add(key)
            annotator_files[role] += 1

    a = annotator_keys.get("Encoder_A", set())
    b = annotator_keys.get("Encoder_B", set())
    documented_union = a | b
    all_analysis = set().union(*annotator_keys.values()) if annotator_keys else set()
    all_keys = score_keys | all_analysis

    complete = score_keys & a & b
    score_a_without_b = (score_keys & a) - b
    score_b_without_a = (score_keys & b) - a
    score_without_documented = score_keys - documented_union
    documented_without_score = documented_union - score_keys
    undocumented_annotators = {
        key: annotator_files[key]
        for key in sorted(annotator_files)
        if key not in DOCUMENTED_ANNOTATORS
    }
    undocumented_keys = set().union(
        *(annotator_keys[key] for key in undocumented_annotators)
    ) if undocumented_annotators else set()
    undocumented_only = undocumented_keys - (score_keys | documented_union)

    blockers: set[str] = set()
    expected_works = {composer: set(works) for composer, works in DOCUMENTED_WORKS.items()}
    for composer in sorted(DOCUMENTED_WORKS):
        missing = sorted(expected_works[composer] - works_seen[composer])
        extra = sorted(works_seen[composer] - expected_works[composer])
        if missing:
            blockers.add(f"DOCUMENTED_WORKS_MISSING:{composer}:{','.join(missing)}")
        if extra:
            blockers.add(f"UNEXPECTED_WORKS:{composer}:{','.join(extra)}")
    if len(all_keys) != DOCUMENTED_PHRASE_COUNT:
        blockers.add(
            f"DOCUMENTED_PHRASE_COUNT_MISMATCH:{DOCUMENTED_PHRASE_COUNT}!={len(all_keys)}"
        )
    for annotator, count in undocumented_annotators.items():
        blockers.add(f"UNDOCUMENTED_ANNOTATOR:{annotator}:{count}")
    if score_a_without_b or score_b_without_a or score_without_documented or documented_without_score:
        blockers.add("INCOMPLETE_SCORE_AB_COVERAGE")

    return TavernStructureReport(
        work_counts={composer: len(works_seen[composer]) for composer in sorted(works_seen)},
        observed_unique_phrase_keys=len(all_keys),
        complete_score_a_b=len(complete),
        score_a_without_b=len(score_a_without_b),
        score_b_without_a=len(score_b_without_a),
        score_without_documented_analysis=len(score_without_documented),
        documented_analysis_without_score=len(documented_without_score),
        undocumented_annotator_file_counts=undocumented_annotators,
        undocumented_only_phrase_keys=len(undocumented_only),
        blockers=tuple(sorted(blockers)),
    )


def analyze_tavern_archive(path: str | Path) -> TavernStructureReport:
    archive = Path(path)
    infos = inspect_zip(archive)
    names = [info.filename for info in infos]
    root = _root_from_names(names)
    logical = [_logical_path(info.filename, root) for info in infos if not info.is_dir()]
    return analyze_logical_paths(logical)


def build_work_family_manifest(*, immutable_revision: str) -> dict[str, object]:
    revision = immutable_revision.strip()
    if not revision:
        raise TavernStructureError("immutable_revision is required")
    families: list[dict[str, object]] = []
    for composer in sorted(DOCUMENTED_WORKS):
        for work in DOCUMENTED_WORKS[composer]:
            token = f"tavern:{composer.casefold()}:{work.casefold()}"
            families.append(
                {
                    "source_corpus": "TAVERN",
                    "source_work_id": f"{composer}/{work}",
                    "composer": composer,
                    "work_id": work,
                    "canonical_work_id": token,
                    "edition_id": f"tavern@{revision}:{composer}/{work}",
                    "duplicate_cluster_id": f"pending-cross-corpus:{token}",
                    "split_group_id": token,
                    "cross_corpus_dedup_status": "PENDING",
                    "split_status": "WITHHELD_PENDING_CROSS_CORPUS_DEDUP",
                    "partition": "QUARANTINE",
                }
            )
    return {
        "schema_version": WORK_FAMILY_SCHEMA,
        "source_corpus": "TAVERN",
        "immutable_revision": revision,
        "work_family_count": len(families),
        "families": families,
        "training_authorized": False,
    }


def canonical_json(data: dict[str, object]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
