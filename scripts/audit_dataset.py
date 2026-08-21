from __future__ import annotations

import argparse
import json
from pathlib import Path

from st_harmonic_training.audit import audit_bundle
from st_harmonic_training.safe_ingest import load_bounded_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Stage 0-H fail-closed dataset audit")
    parser.add_argument("bundle", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--expect-hold", action="store_true")
    mode.add_argument("--expect-pass", action="store_true")
    args = parser.parse_args()

    data = load_bounded_json(args.bundle, max_bytes=5 * 1024 * 1024)
    report = audit_bundle(data)
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))

    if args.expect_hold:
        return 0 if not report.training_authorized else 1
    if args.expect_pass:
        return 0 if report.training_authorized else 1
    return 0 if report.training_authorized else 2


if __name__ == "__main__":
    raise SystemExit(main())
