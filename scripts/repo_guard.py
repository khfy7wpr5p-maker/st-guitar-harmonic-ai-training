from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

MAX_TRACKED_BYTES = 1_048_576
FORBIDDEN_PREFIXES = (
    "data/",
    "datasets/",
    "raw/",
    "downloads/",
    "extracted/",
    "checkpoints/",
    "models/",
    "artifacts/",
    "runs/",
)
FORBIDDEN_SUFFIXES = {
    ".zip", ".tar", ".tgz", ".7z", ".rar", ".gz",
    ".ckpt", ".pt", ".pth", ".onnx", ".h5", ".safetensors",
    ".npy", ".npz", ".wav", ".flac", ".mp3", ".mid", ".midi",
    ".mxl", ".musicxml", ".png", ".jpg", ".jpeg", ".tif", ".tiff",
}
FORBIDDEN_EXACT_NAMES = {".env", "id_rsa", "id_ed25519"}
SECRET_PATTERNS = (
    re.compile("gh" + "p_[A-Za-z0-9]{20,}"),
    re.compile("github" + "_pat_[A-Za-z0-9_]{20,}"),
    re.compile("AKIA" + "[A-Z0-9]{16}"),
    re.compile("-----BEGIN " + "(?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)
TEXT_SCAN_LIMIT = 512_000


def tracked_files(root: Path) -> list[Path]:
    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    names = [item for item in completed.stdout.decode("utf-8").split("\0") if item]
    return [root / name for name in names]


def scan(root: Path) -> list[str]:
    violations: list[str] = []
    for path in tracked_files(root):
        rel = path.relative_to(root).as_posix()
        lower_rel = rel.lower()
        if lower_rel.startswith(FORBIDDEN_PREFIXES):
            violations.append(f"forbidden tracked path: {rel}")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            violations.append(f"forbidden tracked file type: {rel}")
        if path.name in FORBIDDEN_EXACT_NAMES:
            violations.append(f"forbidden secret filename: {rel}")
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            violations.append(f"tracked file missing from worktree: {rel}")
            continue
        if size > MAX_TRACKED_BYTES:
            violations.append(f"tracked file exceeds {MAX_TRACKED_BYTES} bytes: {rel}")
        if size <= TEXT_SCAN_LIMIT:
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for pattern in SECRET_PATTERNS:
                if pattern.search(text):
                    violations.append(f"possible secret material: {rel}")
                    break
    return sorted(set(violations))


def main() -> int:
    root = Path(os.environ.get("REPO_ROOT", Path(__file__).resolve().parents[1])).resolve()
    violations = scan(root)
    if violations:
        print("repository security guard: FAIL", file=sys.stderr)
        for item in violations:
            print(f"- {item}", file=sys.stderr)
        return 1
    print("repository security guard: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
