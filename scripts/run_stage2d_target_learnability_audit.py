from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from st_harmonic_training.offline_experiment import require_locked_runtime
from st_harmonic_training.stage2d_target_learnability import (
    canonical_stage2d_json,
    run_stage2d_target_learnability_from_file,
)


class Stage2DLearnabilityHandoffError(ValueError):
    pass


def _assert_external_output_dir(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved == _REPO_ROOT or _REPO_ROOT in resolved.parents:
        raise Stage2DLearnabilityHandoffError(
            "Stage 2-D outputs must stay outside the Git repository"
        )
    if resolved.exists():
        if resolved.is_symlink():
            raise Stage2DLearnabilityHandoffError("output directory symlink rejected")
        if not resolved.is_dir():
            raise Stage2DLearnabilityHandoffError("output path must be a directory")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit Stage 2-B TRAIN-only specialist target learnability. "
            "No model fitting, model selection, checkpointing, or non-TRAIN target access occurs."
        )
    )
    parser.add_argument(
        "specialist_train_private",
        type=Path,
        help="exact Stage 2-B specialist-train.private.json",
    )
    parser.add_argument(
        "output_dir",
        type=Path,
        help="external output directory outside the Git repository",
    )
    args = parser.parse_args()

    require_locked_runtime()
    output_dir = _assert_external_output_dir(args.output_dir)
    output_file = output_dir / "stage2d-learnability-summary.json"
    if output_file.exists() or output_file.is_symlink():
        raise FileExistsError(f"refusing to overwrite Stage 2-D artifact: {output_file}")

    summary = run_stage2d_target_learnability_from_file(
        args.specialist_train_private
    )
    output_file.write_text(canonical_stage2d_json(summary), encoding="utf-8")
    print(json.dumps(summary, sort_keys=True, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
