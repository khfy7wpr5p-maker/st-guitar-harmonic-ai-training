from __future__ import annotations

import argparse
import json
from pathlib import Path
import stat
import sys

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from st_harmonic_training.stage2g_function_onset_events import (
    canonical_stage2g_json,
    run_stage2g_function_onset_events_from_files,
)
from st_harmonic_training.tavern_raw_label_realization import (
    PINNED_TAVERN_ARCHIVE_SHA256,
)


class Stage2GFunctionOnsetEventHandoffError(ValueError):
    pass


def _reject_existing_symlink_component(path: Path) -> None:
    current = path if path.is_absolute() else Path.cwd() / path
    for candidate in (current, *current.parents):
        if candidate.exists() and candidate.is_symlink():
            raise Stage2GFunctionOnsetEventHandoffError(
                f"output path symlink rejected: {candidate}"
            )


def _assert_external_output_dir(path: Path) -> Path:
    expanded = path.expanduser()
    _reject_existing_symlink_component(expanded)
    resolved = expanded.resolve()
    if resolved == _REPO_ROOT or _REPO_ROOT in resolved.parents:
        raise Stage2GFunctionOnsetEventHandoffError(
            "Stage 2-G private outputs must stay outside the Git repository"
        )
    if resolved.exists():
        if resolved.is_symlink():
            raise Stage2GFunctionOnsetEventHandoffError(
                "output directory symlink rejected"
            )
        meta = resolved.stat()
        if not stat.S_ISDIR(meta.st_mode):
            raise Stage2GFunctionOnsetEventHandoffError(
                "output path must be a directory"
            )
    resolved.mkdir(parents=True, exist_ok=True)
    _reject_existing_symlink_component(resolved)
    return resolved


def _assert_new_outputs(output_dir: Path) -> tuple[Path, Path]:
    private_path = output_dir / "function-onset-events.private.json"
    summary_path = output_dir / "function-onset-events-summary.json"
    for path in (private_path, summary_path):
        if path.exists() or path.is_symlink():
            raise FileExistsError(
                f"refusing to overwrite Stage 2-G artifact: {path}"
            )
    return private_path, summary_path


def _write_new(path: Path, text: str) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize Stage 2-G TRAIN-only private Function ONSET_EVENT targets. "
            "Targets come only from human-selected Encoder Function tokens attached "
            "to validated harmonic onset carriers. No duration/segment inference, "
            "model fitting, model selection, or production authority is opened."
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

    output_dir = _assert_external_output_dir(args.output_dir)
    private_path, summary_path = _assert_new_outputs(output_dir)
    private_payload, summary = run_stage2g_function_onset_events_from_files(
        args.validated_decisions,
        args.tavern_archive,
    )
    _write_new(private_path, canonical_stage2g_json(private_payload))
    _write_new(summary_path, canonical_stage2g_json(summary))
    print(json.dumps(summary, sort_keys=True, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
