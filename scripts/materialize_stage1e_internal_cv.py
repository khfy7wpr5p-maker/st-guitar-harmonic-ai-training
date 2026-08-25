from __future__ import annotations

import argparse
from pathlib import Path

from st_harmonic_training.stage1e_internal_cv import (
    build_stage1e_group_plan_summary,
    build_stage1e_summary,
    canonical_stage1e_json,
    materialize_stage1e_internal_cv_from_file,
)


def _write_or_print(payload: str, output: Path | None) -> None:
    if output is None:
        print(payload, end="")
        return
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"refusing to overwrite Stage 1-E artifact: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(payload, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize the Stage 1-E TRAIN-only grouped internal CV assignment. "
            "Original VALIDATION, CALIBRATION, HOLDOUT, and QUARANTINE remain inaccessible."
        )
    )
    parser.add_argument(
        "training_payload",
        nargs="?",
        type=Path,
        help="private full Stage 1-B training payload manifest",
    )
    parser.add_argument("--group-plan-only", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.group_plan_only:
        if args.training_payload is not None:
            parser.error("training_payload must be omitted with --group-plan-only")
        payload = canonical_stage1e_json(build_stage1e_group_plan_summary())
        _write_or_print(payload, args.output)
        return 0

    if args.training_payload is None:
        parser.error("training_payload is required unless --group-plan-only is used")

    materialized = materialize_stage1e_internal_cv_from_file(args.training_payload)
    result = build_stage1e_summary(materialized) if args.summary_only else materialized
    _write_or_print(canonical_stage1e_json(result), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
