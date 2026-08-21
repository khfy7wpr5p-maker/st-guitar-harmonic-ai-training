from __future__ import annotations

import argparse
from pathlib import Path
import sys

from st_harmonic_training.safe_ingest import IngestSecurityError
from st_harmonic_training.tavern_phrase_gate import (
    TavernPhraseGateError,
    build_tavern_phrase_gate_from_files,
    canonical_phrase_gate_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build deterministic TAVERN phrase admission/adjudication gate evidence."
    )
    parser.add_argument("--structure-evidence", required=True, type=Path)
    parser.add_argument("--lineage-evidence", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        evidence = build_tavern_phrase_gate_from_files(
            args.structure_evidence,
            args.lineage_evidence,
        )
        payload = canonical_phrase_gate_json(evidence)
        if args.output is None:
            sys.stdout.write(payload)
            return 0
        if args.output.exists() and not args.overwrite:
            raise TavernPhraseGateError(f"output already exists: {args.output}")
        if args.output.is_symlink():
            raise TavernPhraseGateError(f"symlink output rejected: {args.output}")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8", newline="\n")
        return 0
    except (TavernPhraseGateError, IngestSecurityError, OSError, ValueError) as exc:
        print(f"TAVERN phrase gate: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
