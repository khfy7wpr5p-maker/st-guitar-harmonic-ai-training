from __future__ import annotations

import argparse
from pathlib import Path
import sys

from st_harmonic_training.safe_ingest import IngestSecurityError
from st_harmonic_training.tavern_adjudication import (
    TavernAdjudicationError,
    build_tavern_adjudication_gate_from_files,
    canonical_adjudication_gate_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate human-only TAVERN adjudication against pinned Stage 0-L evidence."
    )
    parser.add_argument("--comparison", required=True, type=Path)
    parser.add_argument("--human-adjudication", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        gate = build_tavern_adjudication_gate_from_files(
            args.comparison,
            args.human_adjudication,
        )
        payload = canonical_adjudication_gate_json(gate)
        if args.output is None:
            sys.stdout.write(payload)
            return 0
        if args.output.exists() and not args.overwrite:
            raise TavernAdjudicationError(f"output already exists: {args.output}")
        if args.output.is_symlink():
            raise TavernAdjudicationError(f"symlink output rejected: {args.output}")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8", newline="\n")
        return 0
    except (TavernAdjudicationError, IngestSecurityError, OSError, ValueError) as exc:
        print(f"TAVERN adjudication gate: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
