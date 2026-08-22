from __future__ import annotations

import argparse
from pathlib import Path

from st_harmonic_training.safe_ingest import load_bounded_json
from st_harmonic_training.training_payload import (
    build_training_payload_manifest,
    build_training_payload_summary,
    canonical_training_payload_json,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Join frozen TAVERN features, normalized targets and split into a leakage-safe training payload manifest."
    )
    parser.add_argument("features", type=Path)
    parser.add_argument("normalized_targets", type=Path)
    parser.add_argument("reviewed_split", type=Path)
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    payload = build_training_payload_manifest(
        load_bounded_json(args.features),
        load_bounded_json(args.normalized_targets),
        load_bounded_json(args.reviewed_split),
    )
    result = build_training_payload_summary(payload) if args.summary_only else payload
    text = canonical_training_payload_json(result)
    if args.output is None:
        print(text, end="")
    else:
        args.output.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
