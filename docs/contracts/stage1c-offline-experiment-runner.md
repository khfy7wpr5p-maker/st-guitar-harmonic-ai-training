# Stage 1-C — Sealed offline experiment runner

Stage 1-C prepares the first **official** learned-model run without weakening the Stage 1-B safety boundary.

## Runtime

Official execution requires exactly Python `3.12.8`. The runner fails closed on any other runtime. The model remains `fieldwise-multinomial-nb-v1`, dependency-free, seed `0`, with canonical JSON checkpoints.

## Partition isolation

The training process never receives the complete 694-label artifact. A separate local data-engineering step creates only two private shards:

- TRAIN: 487 records / 500 acceptable targets; parameter fitting allowed.
- VALIDATION: 125 records / 154 acceptable targets; evaluation/model-selection evidence only.

`CALIBRATION` and `HOLDOUT` are explicitly skipped and never serialized into these experiment shards. TRAIN and VALIDATION split-group IDs must be disjoint. Augmentation remains TRAIN-only.

Private shard payloads contain derived features and normalized human-valid targets and are therefore **not repository artifacts**. They belong under ignored `/runs/` or another private external location. They must not be committed to this public repository.

## Experiment behavior

The runner:
1. verifies the Stage 1-B final PASS and frozen source/manifests;
2. fits the model on TRAIN only;
3. repeats the fit in reversed record order and requires byte-identical canonical checkpoint output;
4. evaluates on VALIDATION only;
5. compares results to the already-frozen Stage 1-A thresholds;
6. writes the model checkpoint only as an external/private artifact;
7. emits a summary containing metrics and digests, not the checkpoint or target bodies.

Frozen validation thresholds are not changed after observing the run:
- exact normalized-label match >= `0.10`
- variant-aware acceptable-set accuracy >= `0.10`
- Roman-numeral component accuracy >= `0.15`
- functional-component accuracy >= `0.10`

All must pass. Failure keeps the model on HOLD and is scientific evidence for the next representation/model version; thresholds may not be lowered in response.

## Confidence and authority

The v1 model emits `MODEL_SCORE_NOT_PROBABILITY`. No probability claim is permitted before a later CALIBRATION stage. The Stage 1-C runner never reads CALIBRATION.

Even a validation PASS grants at most the already-defined `OFFLINE_SHADOW_ONLY` promotion scope. It does not grant production authority, runtime project mutation, or HOLDOUT access.

## Execution handoff

Repository CI already uses Python `3.12.8`, but this repository is public. Human-adjudicated TRAIN/VALIDATION target bodies must not be published merely to make GitHub Actions training convenient. Therefore the official run requires a **private execution handoff** that supplies the locally generated TRAIN/VALIDATION shards to a locked Python 3.12.8 environment without committing them.
