from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from scripts.enhance_tavern_review_diff_tr import reject_source_symlinks
from st_harmonic_training.tavern_review_diff import TavernReviewDiffError


class TavernReviewDiffCliTests(unittest.TestCase):
    def test_regular_source_tree_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            (source / "index.html").write_text("safe", encoding="utf-8")
            reject_source_symlinks(source)

    def test_nested_source_symlink_fails_closed(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symlink unsupported")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            target = root / "outside.txt"
            target.write_text("outside", encoding="utf-8")
            link = source / "batch-001.html"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation unavailable")
            with self.assertRaises(TavernReviewDiffError):
                reject_source_symlinks(source)


if __name__ == "__main__":
    unittest.main()
