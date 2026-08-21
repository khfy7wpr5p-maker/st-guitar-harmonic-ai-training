from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from st_harmonic_training.tavern_structure import (
    TavernStructureError,
    analyze_tavern_archive,
    build_work_family_manifest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit TAVERN structural provenance without authorizing training.")
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--immutable-revision", required=True)
    parser.add_argument("--structure-output", type=Path)
    parser.add_argument("--work-family-output", type=Path)
    return parser.parse_args()


def _write(path: Path | None, payload: dict[str, object]) -> None:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    if path is None:
        sys.stdout.write(text)
        return
    if path.exists() or path.is_symlink():
        raise TavernStructureError(f"refusing to overwrite output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def main() -> int:
    args = parse_args()
    try:
        report = analyze_tavern_archive(args.archive)
        structure = report.to_dict()
        structure["source_corpus"] = "TAVERN"
        structure["immutable_revision"] = args.immutable_revision
        families = build_work_family_manifest(immutable_revision=args.immutable_revision)
        _write(args.structure_output, structure)
        if args.work_family_output is not None:
            _write(args.work_family_output, families)
        return 0
    except (TavernStructureError, OSError, ValueError) as exc:
        print(f"TAVERN structure audit: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
