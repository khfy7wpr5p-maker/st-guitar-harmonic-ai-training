from __future__ import annotations

import argparse
import json
from pathlib import Path

from st_harmonic_training.offline_experiment import (
    build_experiment_summary,
    canonical_experiment_json,
    run_offline_experiment,
)
from st_harmonic_training.safe_ingest import load_bounded_json
from st_harmonic_training.sparse_nb_model import canonical_model_json

MAX_SHARD_BYTES = 64 * 1024 * 1024


def _write_new(path: Path, text: str) -> None:
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"refusing to overwrite experiment artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the authorized Stage 1-C offline experiment on TRAIN and VALIDATION "
            "private shards only. Python 3.12.8 is enforced."
        )
    )
    parser.add_argument("train_shard", type=Path)
    parser.add_argument("validation_shard", type=Path)
    parser.add_argument("entry_completion", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    result = run_offline_experiment(
        load_bounded_json(args.train_shard, max_bytes=MAX_SHARD_BYTES),
        load_bounded_json(args.validation_shard, max_bytes=MAX_SHARD_BYTES),
        load_bounded_json(args.entry_completion),
    )
    summary = build_experiment_summary(result)
    checkpoint = result["model_checkpoint"]
    if not isinstance(checkpoint, dict):
        raise TypeError("model checkpoint payload malformed")

    _write_new(args.output_dir / "model-checkpoint.private.json", canonical_model_json(checkpoint))
    _write_new(args.output_dir / "experiment-summary.json", canonical_experiment_json(summary))
    print(json.dumps(summary, sort_keys=True, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
