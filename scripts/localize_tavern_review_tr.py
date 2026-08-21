from __future__ import annotations

import argparse
import json
from pathlib import Path

from st_harmonic_training.tavern_review_turkish import (
    localize_score_aware_review_package,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Localize the score-aware TAVERN human-review package into Turkish."
    )
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    manifest = localize_score_aware_review_package(
        args.source_dir,
        args.output_dir,
    )
    print(
        json.dumps(
            {
                "schema_version": manifest["schema_version"],
                "review_ui_language": manifest["review_ui_language"],
                "pair_count": manifest["pair_count"],
                "batch_count": manifest["batch_count"],
                "decision_codes_preserved": manifest["decision_codes_preserved"],
                "decisions_preselected": manifest["decisions_preselected"],
                "gold_assignment_authorized": manifest["gold_assignment_authorized"],
                "partition_assignment_authorized": manifest[
                    "partition_assignment_authorized"
                ],
                "training_authorized": manifest["training_authorized"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
