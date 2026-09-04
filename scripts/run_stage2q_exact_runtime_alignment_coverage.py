#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from st_harmonic_training.stage2q_exact_runtime_alignment_coverage import (  # noqa: E402
    run_stage2q_coverage_audit_from_files,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="TRAIN-only Stage 2-Q exact Stage2G event -> runtime-frame coverage audit"
    )
    parser.add_argument("stage2g_private", help="Stage 2-G private Function onset-event JSON")
    parser.add_argument("tavern_archive", help="Pinned TAVERN ZIP archive")
    args = parser.parse_args()
    summary = run_stage2q_coverage_audit_from_files(
        args.stage2g_private,
        archive_path=args.tavern_archive,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
