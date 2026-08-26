# Stage 2-B — TRAIN-only specialist materialization

## Purpose

Stage 2-B prepares the private development payload for the Stage 2-A specialist-model direction without starting model fitting.

The only eligible original partition is Stage 0-T `TRAIN` (487 records / 18 work families). The materializer derives TRAIN identities before opening harmonic annotation bodies, then reads and normalizes only the selected A/B annotation members for those TRAIN phrases. Original VALIDATION, CALIBRATION, and HOLDOUT annotation bodies are not parsed or materialized into the specialist payload.

## First-wave specialists

The private payload exposes only the three Stage 2-A targets supported by current TAVERN evidence:

- `roman_numeral` → `ROMAN_NUMERAL_SPECIALIST`
- `key` → `KEY_SPECIALIST`
- `phrase` → `FUNCTION_SPECIALIST`

Each specialist target keeps two views:

1. `source_targets` — selected human A/B provenance slots, including null where the source has no supported target;
2. `effective_targets` — canonical unique, non-null values used by a later model boundary.

This preserves reviewed provenance while preventing duplicate normalized variants from receiving accidental double weight.

## Input boundary

Required private inputs:

- exact Stage 0-M 694-decision JSON, SHA-256 `0e53133bf150a101f1b55329c4c5741168fbe7b9ac9a748f221ec07fade1be4a`;
- exact pinned TAVERN ZIP, SHA-256 `b95d85bb3f1e5c0f4ea6df772928d247243485abd93153f0550d6be2fba4fc63`;
- locked Python `3.12.8` runtime.

The decision artifact is validated as a whole before TRAIN identities are derived. Archive structure/inventory integrity may be checked globally, but harmonic annotation text is semantically parsed only for TRAIN phrase/source selections.

## Fold boundary

Stage 2-B reuses the already-pinned Stage 1-E grouped development plan:

- 3 folds;
- 18 TRAIN work families;
- 6 work families per fold;
- group plan SHA-256 `ae15ed507247548907815f8ee1a5586f9fa2384a32d5102e887ddedff52e1a4c`;
- identity-only assignment, never label-aware.

Every TRAIN phrase inherits its fold from `split_group_id`. No work family may cross folds.

## Feature boundary

Stage 2-B carries the existing deterministic label-blind `**kern` bag-of-words feature representation only as a baseline representation for later TRAIN-only experiments. Stage 2-B does not claim this representation is sufficient; the first official v1 HOLD already showed that it is not sufficient as a whole-phrase model representation.

No annotation-derived feature may enter the feature vector.

## Outputs

The command writes outside Git only:

- `specialist-train.private.json` — private TRAIN feature/target/fold rows;
- `specialist-train-summary.json` — bounded summary with counts, manifests, support/missing-target statistics, fold distribution, and authority flags.

Raw annotation text is not serialized. Non-TRAIN target bodies are not serialized. The private payload and any future checkpoints must never be committed.

## Authority

Stage 2-B does **not** authorize model fitting. It only makes TRAIN-only specialist data engineering ready.

The following remain false:

- `training_authorized`
- `model_training_started`
- `original_validation_target_access`
- `calibration_target_access`
- `holdout_target_access`
- `event_level_training_authorized`
- `production_authority`

The deterministic resolver in `st-guitar-harmonic-engine` remains the sole authoritative harmonic decision boundary.

## Next gate

After one exact private Stage 2-B run, review only the bounded summary. If the summary proves 487 TRAIN records, correct 3-fold grouping, expected source hashes, and no authority/access escalation, a separate Stage 2-C contract may authorize TRAIN-only grouped-CV experimentation for the three specialists.

Stage 2-C must not reuse original VALIDATION during iterative model/feature selection. CALIBRATION and HOLDOUT remain separately gated.