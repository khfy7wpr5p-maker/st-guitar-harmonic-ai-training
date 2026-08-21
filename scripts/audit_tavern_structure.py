from __future__ import annotations

import argparse
from pathlib import Path
import sys

from st_harmonic_training.safe_ingest import IngestSecurityError
from st_harmonic_training.tavern_structure import (
    TavernStructureError,
    build_tavern_structure_audit,
    canonical_structure_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit pinned TAVERN work/phrase structure and annotator provenance."
    )
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--immutable-revision", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        audit = build_tavern_structure_audit(
            args.archive,
            immutable_revision=args.immutable_revision,
        )
        payload = canonical_structure_json(audit)
        if args.output is None:
            sys.stdout.write(payload)
            return 0
        if args.output.exists() and not args.overwrite:
            raise TavernStructureError(f"output already exists: {args.output}")
        if args.output.is_symlink():
            raise TavernStructureError(f"symlink output rejected: {args.output}")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8", newline="\n")
        return 0
    except (TavernStructureError, IngestSecurityError, OSError, ValueError) as exc:
        print(f"TAVERN structure audit: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
