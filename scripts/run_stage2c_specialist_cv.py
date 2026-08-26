from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from st_harmonic_training.offline_experiment import require_locked_runtime
from st_harmonic_training.stage2c_specialist_cv import (
    canonical_stage2c_summary_json,
    run_stage2c_specialist_grouped_cv_from_file,
)


class Stage2CRunnerError(ValueError):
    pass


def _assert_external_output_dir(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    repo = _REPO_ROOT
    if resolved == repo or repo in resolved.parents:
        raise Stage2CRunnerError("Stage 2-C outputs must stay outside the Git repository")
    if resolved.exists():
        if resolved.is_symlink():
            raise Stage2CRunnerError("output directory symlink rejected")
        if not resolved.is_dir():
            raise Stage2CRunnerError("output path must be a directory")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _write_new(path: Path, text: str) -> None:
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"refusing to overwrite Stage 2-C artifact: {path}")
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run Stage 2-C TRAIN-only 3-fold grouped CV for the Roman Numeral, "
            "Key, and Function specialists. Original VALIDATION/CALIBRATION/HOLDOUT "
            "remain inaccessible and no final full-TRAIN checkpoint is produced."
        )
    )
    parser.add_argument(
        "stage2b_private_payload",
        type=Path,
        help="exact external specialist-train.private.json from Stage 2-B",
    )
    parser.add_argument(
        "output_dir",
        type=Path,
        help="external output directory for the bounded safe CV summary",
    )
    args = parser.parse_args()

    # Fail before touching private payload bytes when runtime is not exact.
    require_locked_runtime()
    output_dir = _assert_external_output_dir(args.output_dir)
    summary = run_stage2c_specialist_grouped_cv_from_file(
        args.stage2b_private_payload
    )
    _write_new(
        output_dir / "stage2c-cv-summary.json",
        canonical_stage2c_summary_json(summary),
    )
    print(json.dumps(summary, sort_keys=True, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
