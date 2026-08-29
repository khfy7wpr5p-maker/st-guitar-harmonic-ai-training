from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from scripts.materialize_stage2g_function_onset_events import (
    Stage2GFunctionOnsetEventHandoffError,
    _assert_external_output_dir,
)


class Stage2GOutputSymlinkEdgeTests(unittest.TestCase):
    def test_dangling_output_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            link = root / "dangling"
            try:
                link.symlink_to(root / "missing-target", target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation unavailable")
            self.assertTrue(link.is_symlink())
            self.assertFalse(link.exists())
            with self.assertRaises(Stage2GFunctionOnsetEventHandoffError):
                _assert_external_output_dir(link)


if __name__ == "__main__":
    unittest.main()
