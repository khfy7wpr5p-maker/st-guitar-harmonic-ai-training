from __future__ import annotations

import argparse
from pathlib import Path

from st_harmonic_training.tavern_gold_materialization import (
    build_tavern_gold_materialization_from_file,
    build_tavern_gold_materialization_summary,
    canonical_tavern_gold_materialization_json,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build hash-bound TAVERN teacher-gold materialization metadata.")
    parser.add_argument("validated_decisions", type=Path)
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    plan = build_tavern_gold_materialization_from_file(args.validated_decisions)
    result = build_tavern_gold_materialization_summary(plan) if args.summary_only else plan
    payload = canonical_tavern_gold_materialization_json(result)
    if args.output is None:
        print(payload, end="")
    else:
        args.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
