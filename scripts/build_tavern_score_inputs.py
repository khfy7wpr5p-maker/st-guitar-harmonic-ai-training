from __future__ import annotations

import argparse
from pathlib import Path

from st_harmonic_training.tavern_score_input_realization import (
    build_tavern_score_input_realization_from_files,
    build_tavern_score_input_realization_summary,
    canonical_tavern_score_input_json,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reread and hash-bind the 694 reviewed TAVERN score phrase inputs."
    )
    parser.add_argument("validated_decisions", type=Path)
    parser.add_argument("tavern_archive", type=Path)
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    realized = build_tavern_score_input_realization_from_files(
        args.validated_decisions, args.tavern_archive
    )
    result = (
        build_tavern_score_input_realization_summary(realized)
        if args.summary_only
        else realized
    )
    payload = canonical_tavern_score_input_json(result)
    if args.output is None:
        print(payload, end="")
    else:
        args.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
