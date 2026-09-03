from pathlib import Path
import json
import tempfile
import unittest

from st_harmonic_training.stage2l_causal_context_availability_audit import audit, write_summary

TEXT = '''pitch-class mask; bass pitch class; note count.
previous deterministic state; previous resolved identity fields when available; previous bass pitch class.
future/next-frame features; Teacher-Gold labels; frozen HOLDOUT labels; expected/target answers.
'''


class Stage2LCausalContextAvailabilityAuditTests(unittest.TestCase):
    def test_audit_accepts_frozen_causal_contract(self):
        s = audit(TEXT, "eef494d381a308200f502332db85091697bab163")
        self.assertIs(s["next_or_future_context_forbidden"], True)
        self.assertIs(s["inference_time_feature_availability_established"], False)
        self.assertIs(s["model_training_started"], False)
        self.assertIs(s["production_authority"], False)

    def test_engine_pin_fail_closed(self):
        with self.assertRaises(ValueError):
            audit(TEXT, "bad")

    def test_missing_required_marker_fails(self):
        with self.assertRaises(ValueError):
            audit(TEXT.replace("pitch-class mask", "x"), "eef494d381a308200f502332db85091697bab163")

    def test_missing_forbidden_marker_fails(self):
        with self.assertRaises(ValueError):
            audit(TEXT.replace("future/next-frame features", "x"), "eef494d381a308200f502332db85091697bab163")

    def test_write_summary_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "summary.json"
            write_summary({"a": 1}, out)
            with self.assertRaises(FileExistsError):
                write_summary({"a": 2}, out)

    def test_write_summary_refuses_repository_local_output(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "repo"
            root.mkdir()
            with self.assertRaises(ValueError):
                write_summary({"a": 1}, root / "summary.json", forbidden_root=root)

    def test_write_summary_refuses_symlink(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            target = base / "target.json"
            link = base / "link.json"
            target.write_text("x", encoding="utf-8")
            link.symlink_to(target)
            with self.assertRaises(ValueError):
                write_summary({"a": 1}, link)

    def test_write_summary_refuses_symlink_parent_into_repo(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            root = base / "repo"
            root.mkdir()
            link = base / "external"
            link.symlink_to(root, target_is_directory=True)
            with self.assertRaises(ValueError):
                write_summary({"a": 1}, link / "summary.json", forbidden_root=root)

    def test_write_summary_refuses_any_symlink_parent(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            real = base / "real"
            real.mkdir()
            link = base / "external"
            link.symlink_to(real, target_is_directory=True)
            with self.assertRaises(ValueError):
                write_summary({"a": 1}, link / "summary.json")

    def test_write_summary_refuses_dangling_symlink(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            link = base / "dangling"
            link.symlink_to(base / "missing", target_is_directory=True)
            with self.assertRaises(ValueError):
                write_summary({"a": 1}, link / "summary.json")

    def test_summary_is_created_exclusively(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "summary.json"
            write_summary({"a": 1}, out)
            self.assertEqual(json.loads(out.read_text(encoding="utf-8")), {"a": 1})


if __name__ == "__main__":
    unittest.main()
