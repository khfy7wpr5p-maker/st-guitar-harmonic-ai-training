from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
import stat
import xml.etree.ElementTree as ET
import zipfile


class IngestSecurityError(ValueError):
    pass


@dataclass(frozen=True)
class ZipLimits:
    max_archive_bytes: int = 256 * 1024 * 1024
    max_members: int = 20_000
    max_member_bytes: int = 64 * 1024 * 1024
    max_total_uncompressed_bytes: int = 1024 * 1024 * 1024
    max_compression_ratio: float = 200.0


BLOCKED_EXECUTABLE_SUFFIXES = {
    ".exe", ".dll", ".com", ".bat", ".cmd", ".ps1", ".sh", ".bash",
    ".py", ".pyc", ".js", ".mjs", ".jar", ".msi", ".scr",
}


def _bounded_bytes(path: Path, max_bytes: int) -> bytes:
    size = path.stat().st_size
    if size > max_bytes:
        raise IngestSecurityError(f"input exceeds {max_bytes} bytes: {path.name}")
    data = path.read_bytes()
    if len(data) > max_bytes:
        raise IngestSecurityError(f"input exceeds {max_bytes} bytes after read: {path.name}")
    return data


def read_bounded_binary(path: str | Path, *, max_bytes: int) -> bytes:
    return _bounded_bytes(Path(path), max_bytes)


def read_bounded_utf8_text(path: str | Path, *, max_bytes: int) -> str:
    data = _bounded_bytes(Path(path), max_bytes)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IngestSecurityError("input must be valid UTF-8") from exc


def _no_duplicate_json_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise IngestSecurityError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_bounded_json(path: str | Path, *, max_bytes: int = 5 * 1024 * 1024) -> object:
    text = read_bounded_utf8_text(path, max_bytes=max_bytes)
    try:
        return json.loads(text, object_pairs_hook=_no_duplicate_json_keys)
    except IngestSecurityError:
        raise
    except json.JSONDecodeError as exc:
        raise IngestSecurityError(f"malformed JSON: {exc.msg}") from exc


def validate_unique_ids(records: list[dict[str, object]], *, id_key: str = "id") -> None:
    seen: set[str] = set()
    for index, record in enumerate(records):
        value = record.get(id_key)
        if not isinstance(value, str) or not value.strip():
            raise IngestSecurityError(f"record {index} missing non-empty {id_key}")
        if value in seen:
            raise IngestSecurityError(f"duplicate {id_key}: {value}")
        seen.add(value)


def parse_bounded_xml(path: str | Path, *, max_bytes: int = 8 * 1024 * 1024) -> ET.Element:
    text = read_bounded_utf8_text(path, max_bytes=max_bytes)
    upper = text.upper()
    if "<!DOCTYPE" in upper or "<!ENTITY" in upper:
        raise IngestSecurityError("DTD/entity declarations are forbidden")
    try:
        return ET.fromstring(text)
    except ET.ParseError as exc:
        raise IngestSecurityError(f"malformed XML: {exc}") from exc


def _normalized_member_path(name: str) -> PurePosixPath:
    if "\x00" in name:
        raise IngestSecurityError("ZIP member contains NUL")
    normalized_name = name.replace("\\", "/")
    path = PurePosixPath(normalized_name)
    if path.is_absolute():
        raise IngestSecurityError(f"absolute ZIP member path: {name}")
    if not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise IngestSecurityError(f"unsafe ZIP member path: {name}")
    if any(part.endswith(":") for part in path.parts):
        raise IngestSecurityError(f"drive-like ZIP member path: {name}")
    return path


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0xFFFF
    return stat.S_IFMT(mode) == stat.S_IFLNK


def inspect_zip(path: str | Path, *, limits: ZipLimits = ZipLimits()) -> tuple[zipfile.ZipInfo, ...]:
    archive = Path(path)
    if archive.stat().st_size > limits.max_archive_bytes:
        raise IngestSecurityError("ZIP archive exceeds maximum compressed size")

    with zipfile.ZipFile(archive) as zf:
        infos = zf.infolist()
        if len(infos) > limits.max_members:
            raise IngestSecurityError("ZIP contains too many members")

        total_uncompressed = 0
        normalized_names: set[str] = set()
        for info in infos:
            member_path = _normalized_member_path(info.filename)
            normalized = member_path.as_posix()
            if normalized in normalized_names:
                raise IngestSecurityError(f"duplicate ZIP member path: {normalized}")
            normalized_names.add(normalized)

            if _is_symlink(info):
                raise IngestSecurityError(f"symlink ZIP member forbidden: {normalized}")
            if not info.is_dir() and member_path.suffix.lower() in BLOCKED_EXECUTABLE_SUFFIXES:
                raise IngestSecurityError(f"executable/script ZIP member forbidden: {normalized}")
            if info.file_size > limits.max_member_bytes:
                raise IngestSecurityError(f"ZIP member exceeds size limit: {normalized}")

            total_uncompressed += info.file_size
            if total_uncompressed > limits.max_total_uncompressed_bytes:
                raise IngestSecurityError("ZIP total uncompressed size exceeds limit")

            if info.file_size:
                ratio = info.file_size / max(info.compress_size, 1)
                if ratio > limits.max_compression_ratio:
                    raise IngestSecurityError(f"ZIP compression ratio too high: {normalized}")
        return tuple(infos)


def safe_extract_zip(
    path: str | Path,
    destination: str | Path,
    *,
    limits: ZipLimits = ZipLimits(),
) -> list[Path]:
    archive = Path(path)
    infos = inspect_zip(archive, limits=limits)
    root = Path(destination).resolve()
    root.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []

    with zipfile.ZipFile(archive) as zf:
        for info in infos:
            member_path = _normalized_member_path(info.filename)
            target = (root / Path(*member_path.parts)).resolve()
            if not target.is_relative_to(root):
                raise IngestSecurityError(f"ZIP destination escape: {info.filename}")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            written = 0
            with zf.open(info, "r") as source, target.open("wb") as sink:
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > limits.max_member_bytes or written > info.file_size:
                        raise IngestSecurityError(f"ZIP member expanded beyond declared/allowed size: {info.filename}")
                    sink.write(chunk)
            extracted.append(target)
    return extracted
