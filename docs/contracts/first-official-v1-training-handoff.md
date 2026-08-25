# First official v1 training — private execution handoff

Status: **READY FOR PRIVATE INPUTS / TRAINING NOT YET ACCEPTED**.

This handoff executes the already-authorized Stage 1-B5 / Stage 1-C whole-phrase v1 offline experiment. It does not authorize event-level v2 training, CALIBRATION, HOLDOUT, or production use.

## Required private inputs

Exactly two private inputs are supplied by the operator:

1. `TAVERN_Stage0M_Validated_Human_Decisions_694_v1.json`
   - schema: `st-tavern-human-adjudication-v1`
   - decisions: 694
   - required SHA-256: `0e53133bf150a101f1b55329c4c5741168fbe7b9ac9a748f221ec07fade1be4a`
2. the exact pinned TAVERN ZIP
   - source revision: `7cc65dc5365603a92376af50ac71491bea7a16ae`
   - required archive SHA-256: `b95d85bb3f1e5c0f4ea6df772928d247243485abd93153f0550d6be2fba4fc63`

The command also reads the repository-safe `evidence/stage1b_entry_completion.v1.json`, which must remain PASS with `training_scope=OFFLINE_EXPERIMENT_ONLY` and `production_authority=false`.

## Runtime

The official run requires exactly Python `3.12.8`. Any other runtime fails before private input processing.

## One-command execution

Run from the repository root with a private output path outside the repository:

```bash
python scripts/run_first_official_v1_training.py \
  /private/TAVERN_Stage0M_Validated_Human_Decisions_694_v1.json \
  /private/TAVERN-pinned.zip \
  /private/st-guitar-harmony-v1-run
```

Module invocation is also supported:

```bash
python -m scripts.run_first_official_v1_training \
  /private/TAVERN_Stage0M_Validated_Human_Decisions_694_v1.json \
  /private/TAVERN-pinned.zip \
  /private/st-guitar-harmony-v1-run
```

The direct script entrypoint explicitly binds imports to its own repository root, so a fresh checkout does not require an editable install merely to resolve `st_harmonic_training`.

The command performs, in memory:

1. validated-decision SHA/schema/source/human-review checks;
2. TAVERN archive SHA, ZIP safety, selected A/B raw-label hash verification;
3. deterministic normalized target materialization;
4. deterministic reviewed TRAIN/VALIDATION/CALIBRATION/HOLDOUT split reconstruction;
5. hash-bound score-input realization;
6. deterministic label-blind `**kern` feature extraction;
7. TRAIN/VALIDATION private shard construction;
8. exact official private-shard digest verification;
9. canonical normalized acceptable-target set projection at the model boundary;
10. TRAIN-only model fitting;
11. reverse-order refit and byte-identical checkpoint reproducibility check;
12. frozen VALIDATION evaluation.

Intermediate target bodies, feature bodies, and TRAIN/VALIDATION shards are not written to disk by this command.

## Pinned private shard gate

Before fitting, the in-memory source/provenance shards must exactly match:

- TRAIN: 487 records / 500 source-target slots / SHA-256 `d70c99ab3b2823946c893cf7b0e085a6300074244700f136fe346b3f320377e9`
- VALIDATION: 125 records / 154 source-target slots / SHA-256 `2201327a49cf8095829c61a0b98ef07f5384c281d6c6f4ef0d14030a5d4d9dc5`

These target counts are provenance-preserving source slots, not a promise that all normalized labels are distinct. A reviewed `PRESERVE_VARIANTS` record may retain both A and B source slots even when deterministic normalization maps them to the same `NormalizedSTLabel`.

After the pinned shard has been verified, model fitting and validation metrics apply `CANONICAL_NORMALIZED_UNIQUE_SET` semantics: canonically identical normalized labels collapse to one acceptable target for model use. This prevents duplicate source provenance from double-weighting one model class while leaving the pinned private shard bytes, source counts, and A/B evidence unchanged. Distinct normalized variants remain distinct and retain equal per-example weighting.

The experiment summary reports both source-target counts and effective model-target counts so any collapse remains auditable without exposing private target bodies.

CALIBRATION and HOLDOUT are never serialized into the experiment shards and remain sealed.

## Outputs

Only the following files are written, and the output directory is required to be outside the Git repository:

- `model-checkpoint.private.json` — private; never commit;
- `experiment-summary.json` — metrics/digests/counts only; review before any evidence commit.

Existing output files are never overwritten.

## Frozen validation gate

All existing Stage 1-A thresholds remain unchanged:

- exact normalized-label match >= `0.10`;
- variant-aware acceptable-set accuracy >= `0.10`;
- Roman-numeral component accuracy >= `0.15`;
- functional-component accuracy >= `0.10`.

A failed metric keeps v1 on HOLD. Thresholds may not be lowered after observing the result.

A full PASS grants at most the existing `OFFLINE_SHADOW_ONLY` scope. `MODEL_SCORE` remains not-a-probability, CALIBRATION/HOLDOUT stay closed, and `production_authority=false`.
