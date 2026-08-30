#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from st_harmonic_training.stage2h_function_event_cv import (  # noqa: E402
    canonical_stage2h_json,
    run_stage2h_grouped_cv_from_files,
)


class Stage2HFunctionEventCVHandoffError(ValueError):
    pass


def _safe_output_path(raw: str) -> Path:
    path = Path(raw).expanduser()
    if path.exists() and path.is_symlink():
        raise Stage2HFunctionEventCVHandoffError("output symlink rejected")
    resolved = path.resolve(strict=False)
    repo = ROOT.resolve()
    try:
        resolved.relative_to(repo)
    except ValueError:
        pass
    else:
        raise Stage2HFunctionEventCVHandoffError("output inside repository rejected")
    if path.exists():
        raise FileExistsError(f"output already exists: {path}")
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    if parent.is_symlink():
        raise Stage2HFunctionEventCVHandoffError("output parent symlink rejected")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run Stage 2-H TRAIN-only Function ONSET_EVENT work-family grouped CV. "
            "Private Stage 2-B/2-G payloads remain external to Git."
        )
    )
    parser.add_argument("stage2b_private", help="Stage 2-B private TRAIN payload JSON")
    parser.add_argument("stage2g_private", help="Stage 2-G private Function onset-event JSON")
    parser.add_argument(
        "--output",
        help="Optional new external path for the aggregate Stage 2-H summary JSON",
    )
    args = parser.parse_args()

    summary = run_stage2h_grouped_cv_from_files(args.stage2b_private, args.stage2g_private)
    rendered = canonical_stage2h_json(summary)
    if args.output:
        output = _safe_output_path(args.output)
        output.write_text(rendered, encoding="utf-8")
        print(json.dumps({"output": str(output), "summary": summary}, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
