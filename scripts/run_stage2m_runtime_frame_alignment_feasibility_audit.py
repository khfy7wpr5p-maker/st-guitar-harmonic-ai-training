#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from st_harmonic_training.stage2m_runtime_frame_alignment_feasibility_audit import (  # noqa: E402
    current_repository_reality_summary,
)


def main() -> int:
    print(json.dumps(current_repository_reality_summary(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
