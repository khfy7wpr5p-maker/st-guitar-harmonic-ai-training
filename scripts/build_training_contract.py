from __future__ import annotations

import argparse
from pathlib import Path

from st_harmonic_training.safe_ingest import load_bounded_json
from st_harmonic_training.training_contract import (
    build_stage1a_training_contract,
    canonical_training_contract_json,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the frozen Stage 1-A harmonic training contract from Stage 0-U readiness evidence.")
    parser.add_argument("readiness_audit", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    contract = build_stage1a_training_contract(load_bounded_json(args.readiness_audit))
    payload = canonical_training_contract_json(contract)
    if args.output is None:
        print(payload, end="")
    else:
        args.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
