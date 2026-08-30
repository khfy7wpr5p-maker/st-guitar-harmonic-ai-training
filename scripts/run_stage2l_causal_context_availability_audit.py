#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess

from st_harmonic_training.stage2l_causal_context_availability_audit import audit, write_summary


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("engine_checkout", type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    training_root = Path(__file__).resolve().parents[1]
    engine = args.engine_checkout.expanduser().absolute()
    if engine.is_symlink():
        raise ValueError("refusing symlink engine checkout")
    contract = engine / "docs/stage8_feature_contract_v0_1.md"
    if not contract.is_file() or contract.is_symlink():
        raise FileNotFoundError(contract)
    engine_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=engine, text=True).strip()
    summary = audit(contract.read_text(encoding="utf-8"), engine_sha)
    write_summary(summary, args.output, forbidden_root=training_root)
    print("Stage 2-L causal context availability audit PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
