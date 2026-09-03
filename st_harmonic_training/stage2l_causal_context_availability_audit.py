"""Stage 2-L causal inference-time context availability audit.

Contract audit only: no private target body is read, no feature is materialized,
and no model is fit. The engine's frozen Stage 8-B feature contract is the
runtime source of truth.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

EXPECTED_ENGINE_SHA = "eef494d381a308200f502332db85091697bab163"
FORBIDDEN_MARKERS = (
    "future/next-frame features",
    "Teacher-Gold labels",
    "frozen HOLDOUT labels",
    "expected/target answers",
)
REQUIRED_MARKERS = (
    "pitch-class mask",
    "bass pitch class",
    "note count",
    "previous deterministic state",
    "previous resolved identity fields when available",
    "previous bass pitch class",
)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def audit(engine_contract_text: str, engine_sha: str) -> dict:
    if engine_sha != EXPECTED_ENGINE_SHA:
        raise ValueError("engine SHA pin mismatch")
    missing = [m for m in REQUIRED_MARKERS if m not in engine_contract_text]
    if missing:
        raise ValueError(f"required causal contract markers missing: {missing}")
    missing_forbidden = [m for m in FORBIDDEN_MARKERS if m not in engine_contract_text]
    if missing_forbidden:
        raise ValueError(f"forbidden markers missing from engine contract: {missing_forbidden}")
    return {
        "schema_version": "st-stage2l-causal-context-availability-audit-summary-v1",
        "engine_main_sha": engine_sha,
        "engine_feature_contract_sha256": _sha256_text(engine_contract_text),
        "current_runtime_feature_family_contract_present": True,
        "previous_runtime_feature_family_contract_present": True,
        "next_or_future_context_forbidden": True,
        "teacher_gold_as_feature_forbidden": True,
        "tavern_harmonic_token_runtime_equivalence_established": False,
        "event_alignment_to_runtime_frames_established": False,
        "inference_time_feature_availability_established": False,
        "feature_materialization_authorized": False,
        "model_training_started": False,
        "non_train_target_access": False,
        "production_authority": False,
        "deterministic_resolver_remains_authoritative": True,
        "decision": "CAUSAL_RUNTIME_CONTRACT_PRESENT_ALIGNMENT_AUDIT_REQUIRED",
    }


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _has_symlink_component(path: Path) -> bool:
    current = Path(path.anchor) if path.is_absolute() else Path()
    for part in path.parts[1:] if path.is_absolute() else path.parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def write_summary(summary: dict, output: Path, forbidden_root: Path | None = None) -> None:
    raw = output.expanduser().absolute()
    if _has_symlink_component(raw):
        raise ValueError("refusing symlink output path")
    root = forbidden_root.expanduser().resolve() if forbidden_root is not None else None
    if root is not None and _is_within(raw, root):
        raise ValueError("refusing repository-local output")
    parent = raw.parent
    parent.mkdir(parents=True, exist_ok=True)
    resolved_output = parent.resolve() / raw.name
    if root is not None and _is_within(resolved_output, root):
        raise ValueError("refusing repository-local output through symlink")
    if resolved_output.exists() or resolved_output.is_symlink():
        raise FileExistsError(f"refusing overwrite: {resolved_output}")
    payload = (json.dumps(summary, indent=2, sort_keys=True) + "\n").encode("utf-8")
    fd = os.open(resolved_output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
    except Exception:
        try:
            resolved_output.unlink()
        except FileNotFoundError:
            pass
        raise
