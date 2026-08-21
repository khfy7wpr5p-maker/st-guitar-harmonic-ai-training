from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from st_harmonic_training.safe_ingest import IngestSecurityError
from st_harmonic_training.tavern_score_review import (
    TavernScoreReviewError,
    enrich_review_package_with_scores,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add pinned TAVERN score references to a Stage 0-N human review package."
    )
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        summary = enrich_review_package_with_scores(
            args.source_dir,
            args.output_dir,
            args.archive,
        )
        print(json.dumps(summary, sort_keys=True))
        return 0
    except (TavernScoreReviewError, IngestSecurityError, OSError, ValueError) as exc:
        print(f"TAVERN score-aware review: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
