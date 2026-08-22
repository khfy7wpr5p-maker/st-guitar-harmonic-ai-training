# Stage 1-A — Guitar harmony training contract

Stage 1-A freezes how a future harmonic specialist model may be trained. **It does not start training.** The current Stage 0-U readiness gate is HOLD, and the Stage 1-A start guard remains closed.

## Model authority

The model's role is `BOUNDED_ADVISORY_HARMONIC_ANALYSIS_EVIDENCE`. It may never become the authoritative harmony decision or mutate engine state directly. Future integration remains:

`model output → validation → deterministic policy → explainable evidence`

## Source and targets

- source subset: `TAVERN_REVIEWED_694`
- TAVERN revision: `7cc65dc5365603a92376af50ac71491bea7a16ae`
- 641 `GOLD_EXPERT` + 53 `GOLD_VARIANT`
- target normalization: `st-harmony-normalization-v1`
- every selected raw label must be reread and SHA-256 verified before dataloader access
- normalization is deterministic and may not infer missing musical semantics
- `GOLD_VARIANT` uses a set-valued acceptable target; arbitrary collapse to A or B is forbidden

## Split and leakage boundary

Pinned Stage 0-T split:
- seed `st-tavern-split-v1:12`
- TRAIN 487
- VALIDATION 125
- CALIBRATION 41
- HOLDOUT 41

Usage is fixed:
- TRAIN: parameter fitting only
- VALIDATION: early stopping and model selection only
- CALIBRATION: post-selection confidence calibration only
- HOLDOUT: one-way final evaluation after selection and calibration policy freeze

Holdout is forbidden during training, model selection, and promotion-threshold tuning. Augmentation is TRAIN-only. Direct-lineage aliases from When-in-Rome/AugmentedNet inherit the TAVERN work-family partition.

## Evaluation and confidence

Planned metrics are exact normalized-label match, variant-aware acceptable-set accuracy, Roman-numeral component accuracy, and functional-component accuracy. No metric value is claimed in Stage 1-A.

A deterministic non-neural/rule baseline must be established only after normalized targets exist. Promotion thresholds remain `PENDING_BASELINE` and must be frozen before any training start authorization.

Raw model output is `MODEL_SCORE`, not a probability. Probability wording is forbidden for uncalibrated output. Any confidence exposed later must be calibrated using the CALIBRATION partition.

## Reproducibility and artifact security

- Python `3.12.8`
- fixed model seed `0`
- deterministic algorithms required
- dependency lock required
- checkpoints and large model artifacts forbidden in Git
- untrusted pickle loading forbidden
- training inputs read-only
- no executable corpus content

## Current start guard

Stage 0-U currently reports HOLD. Explicit blockers:
- `RAW_LABEL_REALIZATION_PENDING`
- `DETERMINISTIC_NORMALIZATION_PENDING`
- `PROMOTION_THRESHOLDS_PENDING_BASELINE`

Therefore:
- `training_start_guard.pass=false`
- `model_training_started=false`
- `training_authorized=false`

Stage 1-B must not begin until a later evidence-backed change clears every blocker through CI-reviewed contracts. No model training is performed by Stage 1-A.
