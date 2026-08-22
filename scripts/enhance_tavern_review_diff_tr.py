from __future__ import annotations

import argparse
import json
from pathlib import Path

from st_harmonic_training.tavern_review_diff import enhance_review_package


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Add source-bounded Turkish A/B difference explanations to a Stage 0-N2 review package."
    )
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    manifest = enhance_review_package(args.source_dir, args.output_dir)
    print(json.dumps({
        "schema_version": manifest["schema_version"],
        "pair_count": manifest["pair_count"],
        "batch_count": manifest["batch_count"],
        "difference_point_count": manifest["difference_point_count"],
        "semantic_glossary_policy": manifest["semantic_glossary_policy"],
        "undocumented_function_tokens_interpreted": manifest["undocumented_function_tokens_interpreted"],
        "training_authorized": manifest["training_authorized"],
    }, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
