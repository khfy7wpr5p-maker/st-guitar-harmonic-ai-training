from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from st_harmonic_training.safe_ingest import IngestSecurityError
from st_harmonic_training.tavern_review_package import (
    DEFAULT_BATCH_SIZE,
    TavernReviewPackageError,
    write_tavern_review_package_from_files,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build an ephemeral, human-only TAVERN A/B review package from the "
            "hash-pinned archive and Stage 0-L comparison evidence."
        )
    )
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--comparison", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    return parser.parse_args()


def _repository_root(start: Path) -> Path | None:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _reject_unsafe_repo_output(output: Path) -> None:
    repo = _repository_root(Path.cwd())
    if repo is None:
        return
    resolved = output.resolve(strict=False)
    try:
        relative = resolved.relative_to(repo)
    except ValueError:
        return
    # /artifacts is already gitignored and rejected by repo_guard if force-added.
    if not relative.parts or relative.parts[0] != "artifacts":
        raise TavernReviewPackageError(
            "review package contains raw annotation text; inside the repository it "
            "may only be written under the gitignored /artifacts directory"
        )


def main() -> int:
    args = parse_args()
    try:
        _reject_unsafe_repo_output(args.output_dir)
        manifest = write_tavern_review_package_from_files(
            args.archive,
            args.comparison,
            args.output_dir,
            batch_size=args.batch_size,
        )
        summary = {
            "schema_version": manifest["schema_version"],
            "pair_count": manifest["pair_count"],
            "relation_counts": manifest["relation_counts"],
            "batch_size": manifest["batch_size"],
            "batch_count": manifest["batch_count"],
            "raw_annotation_text_in_ephemeral_package": manifest[
                "raw_annotation_text_in_ephemeral_package"
            ],
            "raw_annotation_text_committed": manifest["raw_annotation_text_committed"],
            "decisions_preselected": manifest["decisions_preselected"],
            "gold_assignment_authorized": manifest["gold_assignment_authorized"],
            "partition_assignment_authorized": manifest["partition_assignment_authorized"],
            "training_authorized": manifest["training_authorized"],
        }
        print(json.dumps(summary, sort_keys=True))
        return 0
    except (TavernReviewPackageError, IngestSecurityError, OSError, ValueError) as exc:
        print(f"TAVERN human review package: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
