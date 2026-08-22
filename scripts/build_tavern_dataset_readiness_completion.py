from __future__ import annotations

import argparse
from pathlib import Path

from st_harmonic_training.safe_ingest import load_bounded_json
from st_harmonic_training.tavern_readiness_completion import (
    build_tavern_dataset_readiness_completion,
    canonical_tavern_dataset_readiness_completion_json,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compose Stage 0-U/V/W evidence into the completed TAVERN dataset-readiness gate."
    )
    parser.add_argument("stage0u_audit", type=Path)
    parser.add_argument("stage0v_realization_summary", type=Path)
    parser.add_argument("stage0w_normalization_summary", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = build_tavern_dataset_readiness_completion(
        load_bounded_json(args.stage0u_audit),
        load_bounded_json(args.stage0v_realization_summary),
        load_bounded_json(args.stage0w_normalization_summary),
    )
    payload = canonical_tavern_dataset_readiness_completion_json(result)
    if args.output is None:
        print(payload, end="")
    else:
        args.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
