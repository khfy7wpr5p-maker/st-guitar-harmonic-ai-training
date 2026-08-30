from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.run_stage2h_function_event_cv import (
    Stage2HFunctionEventCVHandoffError,
    _safe_output_path,
)

ROOT = Path(__file__).resolve().parents[1]


class Stage2HCLITests(unittest.TestCase):
    def test_help_bootstraps_direct_script(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/run_stage2h_function_event_cv.py"), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("TRAIN-only", result.stdout)
        self.assertIn("ONSET_EVENT", result.stdout)

    def test_repo_output_is_rejected(self) -> None:
        with self.assertRaises(Stage2HFunctionEventCVHandoffError):
            _safe_output_path(str(ROOT / "stage2h-summary.json"))

    def test_existing_output_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "summary.json"
            path.write_text("existing", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                _safe_output_path(str(path))

    def test_external_new_output_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "summary.json"
            self.assertEqual(_safe_output_path(str(path)), path.resolve())


if __name__ == "__main__":
    unittest.main()
