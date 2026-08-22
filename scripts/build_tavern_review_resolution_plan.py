from __future__ import annotations

import argparse
from pathlib import Path

from st_harmonic_training.safe_ingest import load_bounded_json
from st_harmonic_training.tavern_review_closure import (
    build_tavern_review_resolution_plan,
    canonical_tavern_review_resolution_plan_json,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the fail-closed Stage 0-O TAVERN human-review resolution plan."
    )
    parser.add_argument("summary", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    plan = build_tavern_review_resolution_plan(load_bounded_json(args.summary))
    payload = canonical_tavern_review_resolution_plan_json(plan)
    if args.output is None:
        print(payload, end="")
    else:
        args.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
