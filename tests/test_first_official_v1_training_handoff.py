from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.run_first_official_v1_training import (
    FirstOfficialTrainingHandoffError,
    _assert_external_output_dir,
    _repo_root,
    _write_new,
)


class FirstOfficialV1TrainingHandoffTests(unittest.TestCase):
    def test_output_inside_repository_is_rejected(self) -> None:
        with self.assertRaises(FirstOfficialTrainingHandoffError):
            _assert_external_output_dir(_repo_root() / "runs" / "official-v1")

    def test_external_output_directory_is_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "official-v1"
            resolved = _assert_external_output_dir(target)
            self.assertTrue(resolved.is_dir())
            self.assertEqual(resolved, target.resolve())

    def test_existing_artifact_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "experiment-summary.json"
            path.write_text("existing\n", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                _write_new(path, "replacement\n")
            self.assertEqual(path.read_text(encoding="utf-8"), "existing\n")

    def test_direct_script_help_bootstraps_repository_imports(self) -> None:
        script = _repo_root() / "scripts" / "run_first_official_v1_training.py"
        completed = subprocess.run(
            [sys.executable, str(script), "--help"],
            cwd=_repo_root(),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("first official Stage 1-C v1 training", completed.stdout)


if __name__ == "__main__":
    unittest.main()
