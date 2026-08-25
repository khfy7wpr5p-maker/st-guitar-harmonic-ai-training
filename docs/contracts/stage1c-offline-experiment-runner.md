# Stage 1-C — Sealed offline experiment runner

Stage 1-C prepares the first **official** learned-model run without weakening the Stage 1-B safety boundary.

## Runtime

Official execution requires exactly Python `3.12.8`. The runner fails closed on any other runtime. The model remains `fieldwise-multinomial-nb-v1`, dependency-free, seed `0`, with canonical JSON checkpoints.

## Partition isolation

The training process never receives the complete 694-label artifact as a persistent training file. The private handoff reconstructs only two in-memory experiment shards:

- TRAIN: 487 records / 500 source-target slots; parameter fitting allowed.
- VALIDATION: 125 records / 154 source-target slots; evaluation/model-selection evidence only.

`CALIBRATION` and `HOLDOUT` are explicitly skipped and never serialized into these experiment shards. TRAIN and VALIDATION split-group IDs must be disjoint. Augmentation remains TRAIN-only.

Private shard payloads contain derived features and normalized human-valid targets and are therefore **not repository artifacts**. They belong under ignored `/runs/` or another private external location when materialized by legacy tooling. They must not be committed to this public repository.

## Provenance slots vs model target sets

The pinned shard target counts preserve reviewed source provenance. A `PRESERVE_VARIANTS` record therefore retains both source A and source B slots even when deterministic normalization maps both sources to the same `NormalizedSTLabel`.

The model and validation metrics consume acceptable targets as a mathematical set, not a multiset. After private-shard construction and, for the official run, exact pinned-shard verification, normalized labels are canonicalized and duplicate labels collapse under policy:

`CANONICAL_NORMALIZED_UNIQUE_SET`

This boundary rule has three consequences:

1. source/provenance slots and their pinned shard digests remain unchanged;
2. canonically identical A/B labels cannot double-weight one model class;
3. genuinely distinct normalized variants remain distinct and keep equal per-example weighting.

The experiment summary reports source-target counts separately from effective model-target counts so any collapse remains auditable without publishing target bodies.

## Experiment behavior

The runner:
1. verifies the Stage 1-B final PASS and frozen source/manifests;
2. verifies/constructs the sealed TRAIN and VALIDATION shards while keeping CALIBRATION/HOLDOUT closed;
3. projects source-target slots to canonical unique normalized target sets at the model boundary;
4. fits the model on TRAIN only;
5. repeats the fit in reversed record order and requires byte-identical canonical checkpoint output;
6. evaluates on VALIDATION only using the same target-set semantics;
7. compares results to the already-frozen Stage 1-A thresholds;
8. writes the model checkpoint only as an external/private artifact;
9. emits a summary containing metrics, counts, and digests, not the checkpoint or target bodies.

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

Repository CI uses the locked Python contract but this repository is public. Human-adjudicated TRAIN/VALIDATION target bodies must not be published merely to make GitHub Actions training convenient. Therefore the official run requires a **private execution handoff** that supplies or reconstructs the required private inputs in a locked Python 3.12.8 environment without committing them.
