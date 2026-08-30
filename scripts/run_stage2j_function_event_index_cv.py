#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from st_harmonic_training.stage2j_function_event_index_cv import (  # noqa: E402
    canonical_stage2j_json,
    run_stage2j_grouped_cv_from_files,
)


class Stage2JHandoffError(ValueError):
    pass


def _safe_output_path(raw: str) -> Path:
    path = Path(raw).expanduser()
    if path.exists() and path.is_symlink():
        raise Stage2JHandoffError("output symlink rejected")
    resolved = path.resolve(strict=False)
    repo = ROOT.resolve()
    try:
        resolved.relative_to(repo)
    except ValueError:
        pass
    else:
        raise Stage2JHandoffError("output inside repository rejected")
    if path.exists():
        raise FileExistsError(f"output already exists: {path}")
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    if parent.is_symlink():
        raise Stage2JHandoffError("output parent symlink rejected")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run Stage 2-J TRAIN-only Function event-index grouped CV. "
            "Uses only Stage 2-I-approved event index fields."
        )
    )
    parser.add_argument("stage2b_private", help="Stage 2-B private TRAIN payload JSON")
    parser.add_argument("stage2g_private", help="Stage 2-G private Function onset-event JSON")
    parser.add_argument("--output", help="Optional new external path for aggregate Stage 2-J summary")
    args = parser.parse_args()

    summary = run_stage2j_grouped_cv_from_files(args.stage2b_private, args.stage2g_private)
    rendered = canonical_stage2j_json(summary)
    if args.output:
        output = _safe_output_path(args.output)
        output.write_text(rendered, encoding="utf-8")
        print(json.dumps({"output": str(output), "summary": summary}, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
