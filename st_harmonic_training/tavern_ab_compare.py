from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

from .safe_ingest import IngestSecurityError, inspect_zip, load_bounded_json
from .tavern_phrase_gate import PHRASE_GATE_SCHEMA
from .tavern_structure import (
    ANALYSIS_RE,
    PINNED_TAVERN_RAW_SHA256,
    PINNED_TAVERN_REVISION,
    SCORE_RE,
)

COMPARISON_SCHEMA = "st-tavern-ab-comparison-v1"
MAX_ANALYSIS_MEMBER_BYTES = 2 * 1024 * 1024
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DOCUMENTED_ANNOTATORS = frozenset({"A", "B"})


class TavernABComparisonError(ValueError):
    pass


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _archive_root(infos: tuple[zipfile.ZipInfo, ...]) -> str:
    roots: set[str] = set()
    for info in infos:
        parts = PurePosixPath(info.filename.replace("\\", "/")).parts
        if parts:
            roots.add(parts[0])
    if len(roots) != 1:
        raise TavernABComparisonError("TAVERN archive must have exactly one top-level root")
    root = next(iter(roots))
    if not root.startswith("TAVERN-"):
        raise TavernABComparisonError(f"unexpected TAVERN archive root: {root}")
    return root


def _logical_path(name: str, root: str) -> str:
    path = PurePosixPath(name.replace("\\", "/"))
    if not path.parts or path.parts[0] != root:
        raise TavernABComparisonError(f"member outside TAVERN root: {name}")
    if len(path.parts) == 1:
        return ""
    return PurePosixPath(*path.parts[1:]).as_posix()


def _phrase_key(work_id: str, variation: str, phrase: str) -> str:
    return f"{work_id}:{variation}:{phrase}"


def _validate_phrase_gate(data: object) -> int:
    if not isinstance(data, dict) or data.get("schema_version") != PHRASE_GATE_SCHEMA:
        raise TavernABComparisonError("unsupported TAVERN phrase gate evidence")
    if data.get("source_corpus") != "TAVERN":
        raise TavernABComparisonError("phrase gate source corpus mismatch")
    if data.get("source_revision") != PINNED_TAVERN_REVISION:
        raise TavernABComparisonError("phrase gate revision mismatch")
    for field in (
        "gold_assignment_authorized",
        "partition_assignment_authorized",
        "training_authorized",
    ):
        if data.get(field) is not False:
            raise TavernABComparisonError(f"phrase gate must keep {field}=false")
    count = data.get("teacher_gold_candidate_count")
    if not isinstance(count, int) or count < 0:
        raise TavernABComparisonError("teacher_gold_candidate_count must be non-negative integer")
    queues = data.get("queues")
    if not isinstance(queues, dict):
        raise TavernABComparisonError("phrase gate queues must be an object")
    pair_queue = queues.get("human_pair_adjudication")
    if not isinstance(pair_queue, dict):
        raise TavernABComparisonError("human_pair_adjudication queue missing")
    if pair_queue.get("count") != count:
        raise TavernABComparisonError("phrase gate pair queue count mismatch")
    if pair_queue.get("gold_tier_assigned") is not None:
        raise TavernABComparisonError("A/B queue must not carry a gold tier")
    if pair_queue.get("decision") != "A_B_CONTENT_COMPARISON_REQUIRED":
        raise TavernABComparisonError("unexpected A/B queue decision")
    return count


def _read_member_bounded(zf: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
    if info.file_size > MAX_ANALYSIS_MEMBER_BYTES:
        raise IngestSecurityError(f"analysis member exceeds comparator limit: {info.filename}")
    chunks: list[bytes] = []
    observed = 0
    with zf.open(info, "r") as source:
        while True:
            chunk = source.read(64 * 1024)
            if not chunk:
                break
            observed += len(chunk)
            if observed > MAX_ANALYSIS_MEMBER_BYTES or observed > info.file_size:
                raise IngestSecurityError(
                    f"analysis member expanded beyond declared/allowed size: {info.filename}"
                )
            chunks.append(chunk)
    return b"".join(chunks)


def _canonical_text(data: bytes) -> bytes:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise TavernABComparisonError("analysis member must be valid UTF-8") from exc
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def _relation(a: bytes, b: bytes) -> tuple[str, str, str, str, str]:
    a_raw = hashlib.sha256(a).hexdigest()
    b_raw = hashlib.sha256(b).hexdigest()
    a_text = _canonical_text(a)
    b_text = _canonical_text(b)
    a_text_hash = hashlib.sha256(a_text).hexdigest()
    b_text_hash = hashlib.sha256(b_text).hexdigest()
    if a == b:
        relation = "BYTE_EXACT"
    elif a_text == b_text:
        relation = "TEXT_LINE_ENDING_EQUIVALENT"
    else:
        relation = "TEXT_DIFFERENT"
    return relation, a_raw, b_raw, a_text_hash, b_text_hash


def build_tavern_ab_comparison(
    archive_path: str | Path,
    phrase_gate_evidence: object,
    *,
    expected_raw_archive_sha256: str = PINNED_TAVERN_RAW_SHA256,
) -> dict[str, object]:
    expected_pair_count = _validate_phrase_gate(phrase_gate_evidence)
    expected_hash = expected_raw_archive_sha256.strip().lower()
    if not SHA256_RE.fullmatch(expected_hash):
        raise TavernABComparisonError("expected raw archive SHA-256 must be lowercase hex")

    archive = Path(archive_path)
    if archive.is_symlink():
        raise TavernABComparisonError("symlink archive rejected")
    if not archive.is_file():
        raise TavernABComparisonError("archive must be a regular file")
    observed_hash = _sha256_file(archive)
    if observed_hash != expected_hash:
        raise TavernABComparisonError(
            f"TAVERN raw archive SHA-256 mismatch: expected {expected_hash}, observed {observed_hash}"
        )

    infos = inspect_zip(archive)
    root = _archive_root(infos)
    files = [info for info in infos if not info.is_dir()]
    logical_by_info = {info.filename: _logical_path(info.filename, root) for info in files}
    logical_names = set(logical_by_info.values())
    for required in ("README.md", "LICENSE"):
        if required not in logical_names:
            raise TavernABComparisonError(f"required TAVERN source file missing: {required}")

    scores: set[str] = set()
    analyses: dict[str, dict[str, zipfile.ZipInfo]] = defaultdict(dict)

    for info in sorted(files, key=lambda item: logical_by_info[item.filename]):
        logical = logical_by_info[info.filename]
        parts = PurePosixPath(logical).parts
        if len(parts) < 3 or parts[0] not in {"Beethoven", "Mozart"}:
            continue
        work_id = f"{parts[0]}/{parts[1]}"
        filename = parts[-1]

        if parts[2] == "Krn" and filename.endswith(".krn"):
            match = SCORE_RE.search(filename)
            if match:
                key = _phrase_key(work_id, match.group(1), match.group(2))
                if key in scores:
                    raise TavernABComparisonError(f"duplicate score for phrase {key}")
                scores.add(key)
            continue

        if (
            len(parts) >= 5
            and parts[2] == "Encodings"
            and parts[3].startswith("Encoder_")
            and filename.endswith(".krn")
        ):
            match = ANALYSIS_RE.search(filename)
            if not match:
                raise TavernABComparisonError(f"unparseable primary analysis filename: {logical}")
            annotator = match.group(3).upper()
            directory_annotator = parts[3].removeprefix("Encoder_").upper()
            if directory_annotator != annotator:
                raise TavernABComparisonError(
                    f"analysis annotator path/filename mismatch: {logical}"
                )
            if annotator not in DOCUMENTED_ANNOTATORS:
                continue
            key = _phrase_key(work_id, match.group(1), match.group(2))
            if annotator in analyses[key]:
                raise TavernABComparisonError(
                    f"duplicate analysis:{annotator} for phrase {key}"
                )
            analyses[key][annotator] = info

    pair_keys = sorted(
        key
        for key, values in analyses.items()
        if key in scores and DOCUMENTED_ANNOTATORS.issubset(values)
    )
    if len(pair_keys) != expected_pair_count:
        raise TavernABComparisonError(
            f"A/B pair count mismatch: expected {expected_pair_count}, observed {len(pair_keys)}"
        )

    comparisons: list[dict[str, object]] = []
    relation_counts: Counter[str] = Counter()
    with zipfile.ZipFile(archive) as zf:
        for key in pair_keys:
            a = _read_member_bounded(zf, analyses[key]["A"])
            b = _read_member_bounded(zf, analyses[key]["B"])
            relation, a_raw, b_raw, a_text, b_text = _relation(a, b)
            relation_counts[relation] += 1
            comparisons.append(
                {
                    "phrase_key": key,
                    "relation": relation,
                    "annotator_A_raw_sha256": a_raw,
                    "annotator_B_raw_sha256": b_raw,
                    "annotator_A_canonical_text_sha256": a_text,
                    "annotator_B_canonical_text_sha256": b_text,
                }
            )

    return {
        "schema_version": COMPARISON_SCHEMA,
        "source_corpus": "TAVERN",
        "source_revision": PINNED_TAVERN_REVISION,
        "raw_archive_sha256": observed_hash,
        "comparison_scope": "EVIDENCE_ONLY_NO_SEMANTIC_EQUIVALENCE",
        "pair_count": len(comparisons),
        "relation_counts": {
            key: relation_counts[key] for key in sorted(relation_counts)
        },
        "comparisons": comparisons,
        "adjudication_authorized": False,
        "gold_assignment_authorized": False,
        "partition_assignment_authorized": False,
        "training_authorized": False,
    }


def build_tavern_ab_comparison_from_files(
    archive_path: str | Path,
    phrase_gate_path: str | Path,
    *,
    expected_raw_archive_sha256: str = PINNED_TAVERN_RAW_SHA256,
) -> dict[str, object]:
    return build_tavern_ab_comparison(
        archive_path,
        load_bounded_json(phrase_gate_path),
        expected_raw_archive_sha256=expected_raw_archive_sha256,
    )


def canonical_ab_comparison_json(evidence: dict[str, object]) -> str:
    if evidence.get("schema_version") != COMPARISON_SCHEMA:
        raise TavernABComparisonError("unsupported TAVERN A/B comparison schema")
    return json.dumps(
        evidence,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ) + "\n"
