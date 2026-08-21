from __future__ import annotations

import argparse
from pathlib import Path
import sys

from st_harmonic_training.tavern_evidence import (
    TavernEvidenceError,
    build_tavern_evidence,
    canonical_evidence_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build deterministic TAVERN archive and subset integrity evidence."
    )
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--immutable-revision", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        evidence = build_tavern_evidence(
            args.archive,
            immutable_revision=args.immutable_revision,
        )
        payload = canonical_evidence_json(evidence)
        if args.output is None:
            sys.stdout.write(payload)
            return 0
        if args.output.exists() and not args.overwrite:
            raise TavernEvidenceError(f"output already exists: {args.output}")
        if args.output.is_symlink():
            raise TavernEvidenceError(f"symlink output rejected: {args.output}")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8", newline="\n")
        return 0
    except (TavernEvidenceError, OSError, ValueError) as exc:
        print(f"TAVERN evidence: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
