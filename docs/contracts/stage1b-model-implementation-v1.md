# Stage 1-B4 — Deterministic learned-model implementation v1

This stage resolves only `MODEL_IMPLEMENTATION_PENDING`. It does **not** execute model training and does not grant runtime or production authority.

## Algorithm

The first learned experiment is `fieldwise-multinomial-nb-v1`, a dependency-free sparse multinomial Naive Bayes implementation over the frozen `st-tavern-kern-bow-v1` feature representation.

Each normalized ST harmony field is learned independently. The implementation is intentionally simple so the first experiment can test whether the deterministic surface-token representation contains useful cross-work harmonic evidence before introducing a more complex model.

## Variant preservation

`GOLD_VARIANT` is never collapsed to A or B during fitting. A record with two acceptable normalized targets contributes total training mass `1.0`, divided equally as `0.5 + 0.5` between its two human-valid targets for every modeled field.

## Partition boundary

The fit API accepts only examples explicitly marked `TRAIN`. Supplying a `VALIDATION`, `CALIBRATION`, or `HOLDOUT` example to the fitting path fails closed. Validation evaluation is a separate operation. CALIBRATION remains reserved for post-selection confidence calibration and HOLDOUT remains unavailable until the one-way final evaluation stage.

## Confidence semantics

The raw output is a log-domain `MODEL_SCORE`. It is not a probability. The v1 model exposes `calibrated_probability=null`; probability wording remains forbidden until a later calibration stage uses the CALIBRATION partition.

## Determinism and dependency lock

- Python: `3.12.8`
- model seed: `0`
- external runtime dependencies: none
- implementation: Python standard library only
- smoothing alpha: `1.0`
- vocabulary and class ordering: lexicographically deterministic
- checkpoint: canonical UTF-8 JSON only
- pickle/joblib or executable-object deserialization: forbidden
- large checkpoints: external artifact only, never committed to Git

The canonical model checkpoint contains only learned class/feature counts and algorithm metadata. It does not authorize project-state mutation.

## Authority

After this stage:
- `model_implementation_complete=true`
- `model_training_started=false`
- `training_authorized=false`
- `production_authority=false`

A separate Stage 1-B final entry audit must verify score realization, deterministic features, leakage-safe payload, frozen thresholds, dependency lock, and this implementation before the first offline training run can be authorized.
