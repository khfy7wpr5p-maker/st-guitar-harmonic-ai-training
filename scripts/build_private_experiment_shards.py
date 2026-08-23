from __future__ import annotations

import argparse
import json
from pathlib import Path

from st_harmonic_training.offline_experiment import build_private_experiment_shards
from st_harmonic_training.safe_ingest import load_bounded_json

MAX_JSON_BYTES = 64 * 1024 * 1024


def _write_new(path: Path, payload: dict[str, object]) -> None:
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"refusing to overwrite private shard: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build local TRAIN/VALIDATION experiment shards. CALIBRATION/HOLDOUT "
            "are never serialized by this command. Keep outputs outside Git."
        )
    )
    parser.add_argument("features", type=Path)
    parser.add_argument("normalized_targets", type=Path)
    parser.add_argument("reviewed_split", type=Path)
    parser.add_argument("entry_completion", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    shards = build_private_experiment_shards(
        load_bounded_json(args.features, max_bytes=MAX_JSON_BYTES),
        load_bounded_json(args.normalized_targets, max_bytes=MAX_JSON_BYTES),
        load_bounded_json(args.reviewed_split, max_bytes=MAX_JSON_BYTES),
        load_bounded_json(args.entry_completion),
    )
    _write_new(args.output_dir / "train.private.json", shards["TRAIN"])
    _write_new(args.output_dir / "validation.private.json", shards["VALIDATION"])
    print("Private experiment shards written. Do not commit them to Git.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
