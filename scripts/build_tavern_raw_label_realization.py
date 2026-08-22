from __future__ import annotations

import argparse
from pathlib import Path

from st_harmonic_training.tavern_raw_label_realization import (
    build_tavern_raw_label_realization_from_files,
    build_tavern_raw_label_realization_summary,
    canonical_tavern_raw_label_realization_json,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reread and hash-verify selected TAVERN human-review labels."
    )
    parser.add_argument("validated_decisions", type=Path)
    parser.add_argument("tavern_archive", type=Path)
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    realization = build_tavern_raw_label_realization_from_files(
        args.validated_decisions, args.tavern_archive
    )
    result = (
        build_tavern_raw_label_realization_summary(realization)
        if args.summary_only
        else realization
    )
    payload = canonical_tavern_raw_label_realization_json(result)
    if args.output is None:
        print(payload, end="")
    else:
        args.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
