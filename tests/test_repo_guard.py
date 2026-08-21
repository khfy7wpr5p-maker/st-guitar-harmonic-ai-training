from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.repo_guard import scan


class RepoGuardTests(unittest.TestCase):
    def make_repo(self) -> Path:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        return root

    def track(self, root: Path, relative: str, content: bytes) -> None:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        subprocess.run(["git", "add", "--", relative], cwd=root, check=True)

    def test_clean_manifest_is_allowed(self) -> None:
        root = self.make_repo()
        self.track(root, "manifests/source.json", b'{}\n')
        self.assertEqual(scan(root), [])

    def test_raw_dataset_path_is_rejected(self) -> None:
        root = self.make_repo()
        self.track(root, "datasets/raw/corpus.tsv", b"unsafe\n")
        self.assertTrue(any("forbidden tracked path" in item for item in scan(root)))

    def test_checkpoint_extension_is_rejected(self) -> None:
        root = self.make_repo()
        self.track(root, "candidate.ckpt", b"not-a-real-checkpoint")
        self.assertTrue(any("forbidden tracked file type" in item for item in scan(root)))

    def test_secret_pattern_is_rejected(self) -> None:
        root = self.make_repo()
        fake = ("gh" + "p_" + "A" * 24).encode()
        self.track(root, "config.txt", fake)
        self.assertTrue(any("possible secret material" in item for item in scan(root)))

    def test_large_tracked_file_is_rejected(self) -> None:
        root = self.make_repo()
        self.track(root, "oversized.txt", b"x" * 1_048_577)
        self.assertTrue(any("exceeds" in item for item in scan(root)))


if __name__ == "__main__":
    unittest.main()
