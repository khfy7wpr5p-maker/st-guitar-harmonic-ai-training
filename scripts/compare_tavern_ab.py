from __future__ import annotations

import argparse
from pathlib import Path
import sys

from st_harmonic_training.safe_ingest import IngestSecurityError
from st_harmonic_training.tavern_ab_compare import (
    TavernABComparisonError,
    build_tavern_ab_comparison_from_files,
    canonical_ab_comparison_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare documented TAVERN A/B analysis artifacts without assigning gold."
    )
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--phrase-gate-evidence", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        evidence = build_tavern_ab_comparison_from_files(
            args.archive,
            args.phrase_gate_evidence,
        )
        payload = canonical_ab_comparison_json(evidence)
        if args.output is None:
            sys.stdout.write(payload)
            return 0
        if args.output.exists() and not args.overwrite:
            raise TavernABComparisonError(f"output already exists: {args.output}")
        if args.output.is_symlink():
            raise TavernABComparisonError(f"symlink output rejected: {args.output}")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8", newline="\n")
        return 0
    except (TavernABComparisonError, IngestSecurityError, OSError, ValueError) as exc:
        print(f"TAVERN A/B comparison: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
