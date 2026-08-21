from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

from .safe_ingest import inspect_zip

CHUNK_SIZE = 1024 * 1024
INVENTORY_SCHEMA = "st-corpus-inventory-v1"
EVIDENCE_SCHEMA = "st-tavern-evidence-v1"
COMPOSERS = {"Beethoven", "Mozart"}


class TavernEvidenceError(ValueError):
    pass


@dataclass(frozen=True)
class InventoryEntry:
    path: str
    size_bytes: int
    sha256: str

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _member_sha256(zf: zipfile.ZipFile, info: zipfile.ZipInfo) -> str:
    digest = hashlib.sha256()
    written = 0
    with zf.open(info, "r") as handle:
        while chunk := handle.read(CHUNK_SIZE):
            written += len(chunk)
            if written > info.file_size:
                raise TavernEvidenceError(
                    f"ZIP member expanded beyond declared size: {info.filename}"
                )
            digest.update(chunk)
    if written != info.file_size:
        raise TavernEvidenceError(
            f"ZIP member size mismatch: {info.filename}: {written} != {info.file_size}"
        )
    return digest.hexdigest()


def _archive_root(infos: tuple[zipfile.ZipInfo, ...]) -> str:
    roots: set[str] = set()
    for info in infos:
        normalized = info.filename.replace("\\", "/")
        parts = PurePosixPath(normalized).parts
        if parts:
            roots.add(parts[0])
    if len(roots) != 1:
        raise TavernEvidenceError(
            "TAVERN archive must contain exactly one top-level root directory"
        )
    root = next(iter(roots))
    if not root.startswith("TAVERN-"):
        raise TavernEvidenceError(f"unexpected TAVERN archive root: {root}")
    return root


def _logical_path(name: str, root: str) -> str:
    normalized = PurePosixPath(name.replace("\\", "/"))
    if not normalized.parts or normalized.parts[0] != root:
        raise TavernEvidenceError(f"member outside TAVERN root: {name}")
    if len(normalized.parts) == 1:
        return ""
    return PurePosixPath(*normalized.parts[1:]).as_posix()


def _role_for(logical_path: str) -> str | None:
    path = PurePosixPath(logical_path)
    parts = path.parts
    if path.suffix.lower() != ".krn" or len(parts) < 4:
        return None
    if parts[0] not in COMPOSERS:
        return None
    if parts[2] == "Krn":
        return "score"
    if len(parts) >= 5 and parts[2] == "Encodings" and parts[3].startswith("Encoder_"):
        return "analysis"
    if parts[2] == "Joined":
        return "joined"
    return None


def _canonical_inventory_json(
    *,
    source_corpus: str,
    immutable_revision: str,
    role: str,
    entries: list[InventoryEntry],
) -> str:
    payload = {
        "schema_version": INVENTORY_SCHEMA,
        "source_corpus": source_corpus,
        "immutable_revision": immutable_revision,
        "role": role,
        "entries": [entry.to_dict() for entry in entries],
    }
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ) + "\n"


def _inventory_digest(
    *,
    source_corpus: str,
    immutable_revision: str,
    role: str,
    entries: list[InventoryEntry],
) -> str:
    canonical = _canonical_inventory_json(
        source_corpus=source_corpus,
        immutable_revision=immutable_revision,
        role=role,
        entries=entries,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_tavern_evidence(
    archive_path: str | Path,
    *,
    immutable_revision: str,
    source_corpus: str = "TAVERN",
) -> dict[str, object]:
    archive = Path(archive_path)
    source_corpus = source_corpus.strip()
    immutable_revision = immutable_revision.strip()
    if not source_corpus:
        raise TavernEvidenceError("source_corpus is required")
    if not immutable_revision:
        raise TavernEvidenceError("immutable_revision is required")

    infos = inspect_zip(archive)
    root = _archive_root(infos)
    files = [info for info in infos if not info.is_dir()]
    logical_names = {_logical_path(info.filename, root) for info in files}
    for required in ("README.md", "LICENSE"):
        if required not in logical_names:
            raise TavernEvidenceError(f"required TAVERN source file missing: {required}")

    role_entries: dict[str, list[InventoryEntry]] = {
        "score": [],
        "analysis": [],
        "joined": [],
    }
    excluded_members: list[str] = []
    work_ids: dict[str, set[str]] = {composer: set() for composer in COMPOSERS}
    analysis_annotators: Counter[str] = Counter()
    excluded_extensions: Counter[str] = Counter()

    with zipfile.ZipFile(archive) as zf:
        for info in sorted(files, key=lambda item: _logical_path(item.filename, root)):
            logical = _logical_path(info.filename, root)
            parts = PurePosixPath(logical).parts
            if len(parts) >= 2 and parts[0] in COMPOSERS:
                work_ids[parts[0]].add(parts[1])

            role = _role_for(logical)
            if role is None:
                if logical not in {"README.md", "LICENSE", ".gitignore"}:
                    excluded_members.append(logical)
                    excluded_extensions[PurePosixPath(logical).suffix.lower()] += 1
                continue

            digest = _member_sha256(zf, info)
            role_entries[role].append(
                InventoryEntry(
                    path=logical,
                    size_bytes=info.file_size,
                    sha256=digest,
                )
            )
            if role == "analysis":
                parts = PurePosixPath(logical).parts
                analysis_annotators[parts[3]] += 1

    if not role_entries["score"]:
        raise TavernEvidenceError("TAVERN score inventory is empty")
    if not role_entries["analysis"]:
        raise TavernEvidenceError("TAVERN analysis inventory is empty")

    role_digests = {
        role: _inventory_digest(
            source_corpus=source_corpus,
            immutable_revision=immutable_revision,
            role=role,
            entries=entries,
        )
        for role, entries in role_entries.items()
    }

    return {
        "schema_version": EVIDENCE_SCHEMA,
        "source_corpus": source_corpus,
        "immutable_revision": immutable_revision,
        "raw_archive": {
            "filename": archive.name,
            "size_bytes": archive.stat().st_size,
            "sha256": _sha256_file(archive),
        },
        "manifest_hash_fields": {
            "raw_archive_sha256": _sha256_file(archive),
            "score_sha256": role_digests["score"],
            "analysis_sha256": role_digests["analysis"],
        },
        "derived_validation_evidence": {
            "joined_inventory_sha256": role_digests["joined"],
            "joined_file_count": len(role_entries["joined"]),
        },
        "inventory_counts": {
            "score": len(role_entries["score"]),
            "analysis": len(role_entries["analysis"]),
            "joined": len(role_entries["joined"]),
        },
        "analysis_annotator_counts": {
            key: analysis_annotators[key] for key in sorted(analysis_annotators)
        },
        "work_counts": {
            composer: len(work_ids[composer]) for composer in sorted(COMPOSERS)
        },
        "excluded_member_count": len(excluded_members),
        "excluded_extensions": {
            key: excluded_extensions[key] for key in sorted(excluded_extensions)
        },
        "excluded_members": sorted(excluded_members),
    }


def canonical_evidence_json(evidence: dict[str, object]) -> str:
    if evidence.get("schema_version") != EVIDENCE_SCHEMA:
        raise TavernEvidenceError("unsupported TAVERN evidence schema")
    return json.dumps(
        evidence,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ) + "\n"
