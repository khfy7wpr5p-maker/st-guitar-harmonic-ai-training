# Stage 1-A — Deterministic baseline and promotion-threshold freeze

This stage resolves `PROMOTION_THRESHOLDS_PENDING_BASELINE` without starting a learned model.

The baseline is intentionally trivial and deterministic: count every selected human-valid normalized target in TRAIN, choose the most frequent complete normalized target, and use a lexicographic canonical-JSON tie break. Validation is then evaluated against the acceptable target set. CALIBRATION and HOLDOUT are not read for baseline fitting, baseline evaluation, or threshold tuning.

Real pinned result for `TAVERN_REVIEWED_694`:
- TRAIN records: 487
- TRAIN selected targets: 500
- TRAIN variant records: 13
- unique TRAIN targets: 435
- majority target frequency: 13
- majority target SHA-256: `6bfc22d0bbc7d08e859ad2e6aa53a95fceb478322ad1e4585e4333c756aa7b5e`
- VALIDATION records: 125
- VALIDATION selected targets: 154
- VALIDATION variant records: 29
- exact normalized-label match: `0/125 = 0.00`
- variant-aware acceptable-set accuracy: `0/125 = 0.00`
- Roman-numeral component accuracy: `0/125 = 0.00`
- functional-component accuracy: `5/125 = 0.04`

The poor baseline is useful evidence: phrase-level labels are diverse enough that a train-majority lookup provides almost no validation value. It is only a floor, not a candidate model.

Frozen Stage 1-B validation thresholds are deliberately scoped to **OFFLINE_SHADOW_ONLY**:
- exact normalized-label match >= `0.10`
- variant-aware acceptable-set accuracy >= `0.10`
- Roman-numeral component accuracy >= `0.15`
- functional-component accuracy >= `0.10`

All four thresholds must pass. Full validation coverage, zero leakage violations, and byte-identical deterministic rerun evidence are also mandatory. These thresholds do not authorize production promotion and may not be tuned against HOLDOUT or CALIBRATION.

The threshold floors are intentionally modest because the next allowed state is an offline scientific shadow experiment, not runtime authority. A later production/shadow-to-runtime gate must define materially stronger acceptance requirements from observed model behavior without using HOLDOUT for iterative tuning.

Authority remains fail-closed:
- `model_training_started=false`
- `training_authorized=false`
- `production_promotion_authorized=false`

Resolving this blocker only permits a separate Stage 1-B entry audit to decide whether all input-realization, reproducibility, dependency-lock, artifact-safety, and execution prerequisites are actually present before a training process may run.
