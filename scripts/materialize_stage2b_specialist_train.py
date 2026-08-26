from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from st_harmonic_training.offline_experiment import require_locked_runtime
from st_harmonic_training.stage2b_specialist_materialization import (
    build_stage2b_summary,
    canonical_stage2b_json,
    materialize_stage2b_specialist_train_from_files,
)
from st_harmonic_training.tavern_raw_label_realization import (
    PINNED_TAVERN_ARCHIVE_SHA256,
)


class Stage2BMaterializationHandoffError(ValueError):
    pass


def _assert_external_output_dir(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    repo = _REPO_ROOT
    if resolved == repo or repo in resolved.parents:
        raise Stage2BMaterializationHandoffError(
            "Stage 2-B private outputs must stay outside the Git repository"
        )
    if resolved.exists():
        if resolved.is_symlink():
            raise Stage2BMaterializationHandoffError("output directory symlink rejected")
        if not resolved.is_dir():
            raise Stage2BMaterializationHandoffError("output path must be a directory")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _write_new(path: Path, text: str) -> None:
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"refusing to overwrite Stage 2-B artifact: {path}")
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize the Stage 2-B TRAIN-only private specialist payload. "
            "No model fitting occurs. Original VALIDATION/CALIBRATION/HOLDOUT "
            "annotation bodies are not materialized into this payload."
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
        help="private output directory outside the Git repository",
    )
    args = parser.parse_args()

    # Keep private materialization deterministic under the same exact runtime as
    # the official v1 handoff. Fail before touching private inputs otherwise.
    require_locked_runtime()
    output_dir = _assert_external_output_dir(args.output_dir)

    private_payload = materialize_stage2b_specialist_train_from_files(
        args.validated_decisions,
        args.tavern_archive,
    )
    summary = build_stage2b_summary(private_payload)

    _write_new(
        output_dir / "specialist-train.private.json",
        canonical_stage2b_json(private_payload),
    )
    _write_new(
        output_dir / "specialist-train-summary.json",
        canonical_stage2b_json(summary),
    )

    print(json.dumps(summary, sort_keys=True, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
