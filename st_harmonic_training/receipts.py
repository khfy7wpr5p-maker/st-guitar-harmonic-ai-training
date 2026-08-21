from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

ARTIFACT_ROLES = ("raw_archive", "score", "analysis")
CHUNK_SIZE = 1024 * 1024


class ReceiptError(ValueError):
    pass


@dataclass(frozen=True)
class ArtifactEvidence:
    role: str
    filename: str
    size_bytes: int
    sha256: str

    def as_dict(self) -> dict[str, object]:
        return {
            "role": self.role,
            "filename": self.filename,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }


def _regular_file(path: Path) -> os.stat_result:
    if path.is_symlink():
        raise ReceiptError(f"symlink input rejected: {path}")
    try:
        metadata = path.stat()
    except OSError as exc:
        raise ReceiptError(f"cannot stat input: {path}") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise ReceiptError(f"non-regular input rejected: {path}")
    return metadata


def hash_artifact(role: str, path: Path) -> ArtifactEvidence:
    if role not in ARTIFACT_ROLES:
        raise ReceiptError(f"unknown artifact role: {role}")
    path = Path(path)
    metadata = _regular_file(path)
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(CHUNK_SIZE):
                digest.update(chunk)
    except OSError as exc:
        raise ReceiptError(f"cannot read input: {path}") from exc
    return ArtifactEvidence(
        role=role,
        filename=path.name,
        size_bytes=metadata.st_size,
        sha256=digest.hexdigest(),
    )


def build_receipt(
    source_corpus: str,
    immutable_revision: str,
    artifacts: Mapping[str, Path],
) -> dict[str, object]:
    source_corpus = source_corpus.strip()
    immutable_revision = immutable_revision.strip()
    if not source_corpus:
        raise ReceiptError("source_corpus is required")
    if not immutable_revision:
        raise ReceiptError("immutable_revision is required")
    if not artifacts:
        raise ReceiptError("at least one artifact is required")
    unknown = sorted(set(artifacts) - set(ARTIFACT_ROLES))
    if unknown:
        raise ReceiptError(f"unknown artifact roles: {', '.join(unknown)}")

    resolved_paths: dict[Path, str] = {}
    evidence: list[ArtifactEvidence] = []
    for role in ARTIFACT_ROLES:
        if role not in artifacts:
            continue
        path = Path(artifacts[role])
        _regular_file(path)
        try:
            resolved = path.resolve(strict=True)
        except OSError as exc:
            raise ReceiptError(f"cannot resolve input: {path}") from exc
        if resolved in resolved_paths:
            raise ReceiptError(
                f"same file cannot satisfy multiple roles: {resolved_paths[resolved]} and {role}"
            )
        resolved_paths[resolved] = role
        evidence.append(hash_artifact(role, path))

    return {
        "schema_version": "artifact-receipt-v1",
        "source_corpus": source_corpus,
        "immutable_revision": immutable_revision,
        "artifacts": [item.as_dict() for item in evidence],
    }


def canonical_receipt_json(receipt: Mapping[str, object]) -> str:
    return json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"


def manifest_hash_fields(receipt: Mapping[str, object]) -> dict[str, str | None]:
    if receipt.get("schema_version") != "artifact-receipt-v1":
        raise ReceiptError("unsupported receipt schema")
    raw_artifacts = receipt.get("artifacts")
    if not isinstance(raw_artifacts, list):
        raise ReceiptError("receipt artifacts must be a list")

    result = {f"{role}_sha256": None for role in ARTIFACT_ROLES}
    seen: set[str] = set()
    for raw in raw_artifacts:
        if not isinstance(raw, dict):
            raise ReceiptError("artifact evidence must be an object")
        role = raw.get("role")
        digest = raw.get("sha256")
        if role not in ARTIFACT_ROLES:
            raise ReceiptError(f"unknown artifact role: {role}")
        if role in seen:
            raise ReceiptError(f"duplicate artifact role: {role}")
        if not isinstance(digest, str) or len(digest) != 64:
            raise ReceiptError(f"invalid SHA-256 for role: {role}")
        try:
            int(digest, 16)
        except ValueError as exc:
            raise ReceiptError(f"invalid SHA-256 for role: {role}") from exc
        seen.add(role)
        result[f"{role}_sha256"] = digest.lower()
    return result
