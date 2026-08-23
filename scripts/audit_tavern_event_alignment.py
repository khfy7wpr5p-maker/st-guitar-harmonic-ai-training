from __future__ import annotations

import argparse
from pathlib import Path

from st_harmonic_training.tavern_event_alignment_audit import (
    build_tavern_event_alignment_audit_from_files,
    build_tavern_event_alignment_summary,
    canonical_tavern_event_alignment_json,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit TAVERN Joined files only as source-derived event-alignment carriers. "
            "Joined harmonic labels never become targets."
        )
    )
    parser.add_argument("validated_decisions", type=Path)
    parser.add_argument("tavern_archive", type=Path)
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    audit = build_tavern_event_alignment_audit_from_files(
        args.validated_decisions, args.tavern_archive
    )
    result = build_tavern_event_alignment_summary(audit) if args.summary_only else audit
    payload = canonical_tavern_event_alignment_json(result)
    if args.output is None:
        print(payload, end="")
    else:
        if args.output.exists() or args.output.is_symlink():
            raise FileExistsError(f"refusing to overwrite audit artifact: {args.output}")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
