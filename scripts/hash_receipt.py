from __future__ import annotations

import argparse
import sys
from pathlib import Path

from st_harmonic_training.receipts import ReceiptError, build_receipt, canonical_receipt_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Hash local dataset artifacts without committing corpus payloads."
    )
    parser.add_argument("--source-corpus", required=True)
    parser.add_argument("--immutable-revision", required=True)
    parser.add_argument("--raw-archive", type=Path)
    parser.add_argument("--score", type=Path)
    parser.add_argument("--analysis", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifacts = {
        role: path
        for role, path in (
            ("raw_archive", args.raw_archive),
            ("score", args.score),
            ("analysis", args.analysis),
        )
        if path is not None
    }
    try:
        receipt = build_receipt(args.source_corpus, args.immutable_revision, artifacts)
        payload = canonical_receipt_json(receipt)
        if args.output is None:
            sys.stdout.write(payload)
            return 0
        if args.output.exists() and not args.overwrite:
            raise ReceiptError(f"output already exists: {args.output}")
        if args.output.is_symlink():
            raise ReceiptError(f"symlink output rejected: {args.output}")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8", newline="\n")
        return 0
    except ReceiptError as exc:
        print(f"artifact receipt: FAIL: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"artifact receipt: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
