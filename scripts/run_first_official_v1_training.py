from __future__ import annotations

import argparse
import json
from pathlib import Path
import stat
import sys

# Direct script execution sets sys.path[0] to scripts/. Bind imports to this
# script's repository root so the documented one-command handoff works in a
# fresh checkout without requiring an editable install first.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from st_harmonic_training.offline_experiment import (
    build_experiment_summary,
    build_private_experiment_shards,
    canonical_experiment_json,
    require_locked_runtime,
)
from st_harmonic_training.official_experiment_gate import (
    run_official_offline_experiment,
    validate_pinned_private_shard,
)
from st_harmonic_training.safe_ingest import load_bounded_json
from st_harmonic_training.sparse_nb_model import canonical_model_json
from st_harmonic_training.tavern_kern_features import build_tavern_kern_features
from st_harmonic_training.tavern_normalization_adapter import (
    build_tavern_normalized_targets,
)
from st_harmonic_training.tavern_raw_label_realization import (
    PINNED_TAVERN_ARCHIVE_SHA256,
    build_tavern_raw_label_realization_from_files,
)
from st_harmonic_training.tavern_reviewed_split import (
    build_tavern_reviewed_split_from_file,
)
from st_harmonic_training.tavern_score_input_realization import (
    build_tavern_score_input_realization_from_files,
)

ENTRY_COMPLETION = Path("evidence/stage1b_entry_completion.v1.json")
MAX_ENTRY_BYTES = 1024 * 1024


class FirstOfficialTrainingHandoffError(ValueError):
    pass


def _repo_root() -> Path:
    return _REPO_ROOT


def _assert_external_output_dir(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    repo = _repo_root()
    if resolved == repo or repo in resolved.parents:
        raise FirstOfficialTrainingHandoffError(
            "official training outputs must stay outside the Git repository"
        )
    if resolved.exists():
        if resolved.is_symlink():
            raise FirstOfficialTrainingHandoffError("output directory symlink rejected")
        if not resolved.is_dir():
            raise FirstOfficialTrainingHandoffError("output path must be a directory")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _write_new(path: Path, text: str) -> None:
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"refusing to overwrite official training artifact: {path}")
    path.write_text(text, encoding="utf-8")


def _build_verified_private_shards(
    decisions_path: Path,
    archive_path: Path,
    entry_completion: object,
) -> tuple[dict[str, object], dict[str, object]]:
    realization = build_tavern_raw_label_realization_from_files(
        decisions_path, archive_path
    )
    normalized_targets = build_tavern_normalized_targets(
        realization, archive_path=archive_path
    )
    score_inputs = build_tavern_score_input_realization_from_files(
        decisions_path, archive_path
    )
    features = build_tavern_kern_features(score_inputs, archive_path=archive_path)
    reviewed_split = build_tavern_reviewed_split_from_file(decisions_path)

    shards = build_private_experiment_shards(
        features,
        normalized_targets,
        reviewed_split,
        entry_completion,
    )
    train = validate_pinned_private_shard(shards["TRAIN"], "TRAIN")
    validation = validate_pinned_private_shard(shards["VALIDATION"], "VALIDATION")
    return train, validation


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the first official Stage 1-C v1 training from the exact private "
            "694-decision artifact and pinned TAVERN ZIP. Intermediate target/feature "
            "payloads and TRAIN/VALIDATION shards remain in memory and are never "
            "written by this command."
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
    parser.add_argument(
        "--entry-completion",
        type=Path,
        default=ENTRY_COMPLETION,
        help="Stage 1-B final PASS evidence (defaults to repository evidence file)",
    )
    args = parser.parse_args()

    # Fail before touching private data when the official runtime is not exact.
    require_locked_runtime()
    output_dir = _assert_external_output_dir(args.output_dir)
    entry_completion = load_bounded_json(
        args.entry_completion, max_bytes=MAX_ENTRY_BYTES
    )

    train, validation = _build_verified_private_shards(
        args.validated_decisions,
        args.tavern_archive,
        entry_completion,
    )

    result = run_official_offline_experiment(
        train,
        validation,
        entry_completion,
    )
    summary = build_experiment_summary(result)
    checkpoint = result.get("model_checkpoint")
    if not isinstance(checkpoint, dict):
        raise TypeError("model checkpoint payload malformed")

    _write_new(
        output_dir / "model-checkpoint.private.json",
        canonical_model_json(checkpoint),
    )
    _write_new(
        output_dir / "experiment-summary.json",
        canonical_experiment_json(summary),
    )

    print(json.dumps(summary, sort_keys=True, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
