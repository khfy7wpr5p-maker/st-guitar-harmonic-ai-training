from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from st_harmonic_training.offline_experiment import require_locked_runtime
from st_harmonic_training.stage2f_function_alignment import (
    canonical_stage2f_json,
    run_stage2f_function_alignment_from_files,
)
from st_harmonic_training.tavern_raw_label_realization import (
    PINNED_TAVERN_ARCHIVE_SHA256,
)


class Stage2FFunctionAlignmentHandoffError(ValueError):
    pass


def _assert_external_output_dir(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved == _REPO_ROOT or _REPO_ROOT in resolved.parents:
        raise Stage2FFunctionAlignmentHandoffError(
            "Stage 2-F audit output must stay outside the Git repository"
        )
    if resolved.exists():
        if resolved.is_symlink():
            raise Stage2FFunctionAlignmentHandoffError("output directory symlink rejected")
        if not resolved.is_dir():
            raise Stage2FFunctionAlignmentHandoffError("output path must be a directory")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _write_new(path: Path, text: str) -> None:
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"refusing to overwrite Stage 2-F artifact: {path}")
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Stage 2-F TRAIN-only Function event-carrier alignment audit. "
            "No Function target values, per-record diagnostics, event targets, or "
            "model checkpoints are serialized."
        )
    )
    parser.add_argument(
        "validated_decisions",
        type=Path,
        help="exact TAVERN Stage 0-M validated 694-decision JSON",
    )
    parser.add_argument(
        "tavern_archive",
        type=Path,
        help=(
            "exact pinned TAVERN ZIP; expected SHA-256 "
            + PINNED_TAVERN_ARCHIVE_SHA256
        ),
    )
    parser.add_argument(
        "output_dir",
        type=Path,
        help="external output directory outside the Git repository",
    )
    args = parser.parse_args()

    require_locked_runtime()
    output_dir = _assert_external_output_dir(args.output_dir)
    summary = run_stage2f_function_alignment_from_files(
        args.validated_decisions,
        args.tavern_archive,
    )
    _write_new(
        output_dir / "stage2f-function-alignment-summary.json",
        canonical_stage2f_json(summary),
    )
    print(json.dumps(summary, sort_keys=True, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
