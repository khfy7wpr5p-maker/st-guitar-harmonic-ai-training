from pathlib import Path
import json
import pytest

from st_harmonic_training.stage2l_causal_context_availability_audit import audit, write_summary

TEXT = '''pitch-class mask; bass pitch class; note count.
previous deterministic state; previous resolved identity fields when available; previous bass pitch class.
future/next-frame features; Teacher-Gold labels; frozen HOLDOUT labels; expected/target answers.
'''


def test_audit_accepts_frozen_causal_contract():
    s = audit(TEXT, "eef494d381a308200f502332db85091697bab163")
    assert s["next_or_future_context_forbidden"] is True
    assert s["inference_time_feature_availability_established"] is False
    assert s["model_training_started"] is False
    assert s["production_authority"] is False


def test_engine_pin_fail_closed():
    with pytest.raises(ValueError):
        audit(TEXT, "bad")


def test_missing_required_marker_fails():
    with pytest.raises(ValueError):
        audit(TEXT.replace("pitch-class mask", "x"), "eef494d381a308200f502332db85091697bab163")


def test_missing_forbidden_marker_fails():
    with pytest.raises(ValueError):
        audit(TEXT.replace("future/next-frame features", "x"), "eef494d381a308200f502332db85091697bab163")


def test_write_summary_refuses_overwrite(tmp_path: Path):
    out = tmp_path / "summary.json"
    write_summary({"a": 1}, out)
    with pytest.raises(FileExistsError):
        write_summary({"a": 2}, out)


def test_write_summary_refuses_repository_local_output(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    with pytest.raises(ValueError):
        write_summary({"a": 1}, root / "summary.json", forbidden_root=root)


def test_write_summary_refuses_symlink(tmp_path: Path):
    target = tmp_path / "target.json"
    link = tmp_path / "link.json"
    target.write_text("x", encoding="utf-8")
    link.symlink_to(target)
    with pytest.raises(ValueError):
        write_summary({"a": 1}, link)


def test_write_summary_refuses_symlink_parent_into_repo(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    link = tmp_path / "external"
    link.symlink_to(root, target_is_directory=True)
    with pytest.raises(ValueError):
        write_summary({"a": 1}, link / "summary.json", forbidden_root=root)


def test_write_summary_refuses_any_symlink_parent(tmp_path: Path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "external"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError):
        write_summary({"a": 1}, link / "summary.json")


def test_write_summary_refuses_dangling_symlink(tmp_path: Path):
    link = tmp_path / "dangling"
    link.symlink_to(tmp_path / "missing", target_is_directory=True)
    with pytest.raises(ValueError):
        write_summary({"a": 1}, link / "summary.json")


def test_summary_is_created_exclusively(tmp_path: Path):
    out = tmp_path / "summary.json"
    write_summary({"a": 1}, out)
    assert json.loads(out.read_text(encoding="utf-8")) == {"a": 1}
