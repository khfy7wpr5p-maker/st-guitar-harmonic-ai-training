from __future__ import annotations

import argparse
from pathlib import Path

from st_harmonic_training.tavern_kern_features import (
    build_tavern_kern_features,
    build_tavern_kern_features_summary,
    canonical_tavern_kern_feature_json,
)
from st_harmonic_training.tavern_score_input_realization import (
    build_tavern_score_input_realization_from_files,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build deterministic label-blind **kern features for reviewed TAVERN score phrases."
    )
    parser.add_argument("validated_decisions", type=Path)
    parser.add_argument("tavern_archive", type=Path)
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    score_inputs = build_tavern_score_input_realization_from_files(
        args.validated_decisions, args.tavern_archive
    )
    features = build_tavern_kern_features(
        score_inputs, archive_path=args.tavern_archive
    )
    result = build_tavern_kern_features_summary(features) if args.summary_only else features
    payload = canonical_tavern_kern_feature_json(result)
    if args.output is None:
        print(payload, end="")
    else:
        args.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
