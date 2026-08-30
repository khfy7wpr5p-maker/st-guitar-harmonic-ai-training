#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from st_harmonic_training.stage2i_function_event_feature_audit import (  # noqa: E402
    canonical_stage2i_json,
    run_stage2i_audit_from_file,
)


class Stage2IAuditHandoffError(ValueError):
    pass


def _safe_output_path(raw: str) -> Path:
    path = Path(raw).expanduser()
    if path.exists() and path.is_symlink():
        raise Stage2IAuditHandoffError("output symlink rejected")
    resolved = path.resolve(strict=False)
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError:
        pass
    else:
        raise Stage2IAuditHandoffError("output inside repository rejected")
    if path.exists():
        raise FileExistsError(f"output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink():
        raise Stage2IAuditHandoffError("output parent symlink rejected")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit existing Stage 2-G Function event identity/order fields. No model fitting."
    )
    parser.add_argument("stage2g_private", help="Stage 2-G private Function onset-event payload")
    parser.add_argument("--output", help="Optional new external path for aggregate summary JSON")
    args = parser.parse_args()

    summary = run_stage2i_audit_from_file(args.stage2g_private)
    rendered = canonical_stage2i_json(summary)
    if args.output:
        output = _safe_output_path(args.output)
        output.write_text(rendered, encoding="utf-8")
        print(json.dumps({"output": str(output), "summary": summary}, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
