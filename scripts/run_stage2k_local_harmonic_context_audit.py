#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from st_harmonic_training.stage2k_local_harmonic_context_audit import (  # noqa: E402
    canonical_stage2k_json,
    run_stage2k_audit_from_files,
)


class Stage2KHandoffError(ValueError):
    pass


def _safe_output_path(raw: str) -> Path:
    path = Path(raw).expanduser()
    if path.exists() and path.is_symlink():
        raise Stage2KHandoffError("output symlink rejected")
    resolved = path.resolve(strict=False)
    repo = ROOT.resolve()
    try:
        resolved.relative_to(repo)
    except ValueError:
        pass
    else:
        raise Stage2KHandoffError("output inside repository rejected")
    if path.exists():
        raise FileExistsError(f"output already exists: {path}")
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    if parent.is_symlink():
        raise Stage2KHandoffError("output parent symlink rejected")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Stage 2-K TRAIN-only local harmonic-context feasibility audit."
    )
    parser.add_argument("stage2g_private", help="Stage 2-G private Function onset-event payload")
    parser.add_argument("tavern_archive", help="Pinned TAVERN archive ZIP")
    parser.add_argument("--output", help="Optional new external path for aggregate Stage 2-K summary")
    args = parser.parse_args()

    summary = run_stage2k_audit_from_files(args.stage2g_private, args.tavern_archive)
    rendered = canonical_stage2k_json(summary)
    if args.output:
        output = _safe_output_path(args.output)
        output.write_text(rendered, encoding="utf-8")
        print(json.dumps({"output": str(output), "summary": summary}, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
