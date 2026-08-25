# Stage 2-A — Specialist model decomposition

Status: **ARCHITECTURE CONTRACT / TRAINING NOT AUTHORIZED BY THIS STAGE**.

Stage 2-A responds to the first official whole-phrase v1 validation HOLD by decomposing harmonic learning into bounded specialist tasks while preserving the deterministic resolver as the only authority boundary.

## Motivation

The first official `fieldwise-multinomial-nb-v1` run completed deterministically but did not meet any frozen validation threshold. This stage does not lower thresholds, reopen CALIBRATION/HOLDOUT, or promote the failed checkpoint. Instead it narrows the learned tasks so each model can be measured and improved independently.

## First specialist wave

The current TAVERN normalization adapter and committed Stage 0-W summary support exactly these first-wave specialists:

1. `ROMAN_NUMERAL_SPECIALIST`
   - target field: `roman_numeral`
   - source support: every normalized target must contain harmonic tokens; the adapter rejects labels without harmonic data.
2. `KEY_SPECIALIST`
   - target field: `key`
   - evidence: 692 of 747 normalized targets contain an explicit key.
3. `FUNCTION_SPECIALIST`
   - target field: `phrase`
   - evidence: 739 of 747 normalized targets have a function spine.

The following are **not authorized specialist targets in Stage 2-A**:

- `local_key`: only 1 of 747 normalized targets reports a key-change sequence, which is insufficient for a first-wave specialist;
- `bass`, `inversion`, `chord_family`, `extension`, `suspension`, `alteration`, `cadence`: the current TAVERN adapter materializes these as `null`, so this corpus does not provide supervised targets for them.

## Architecture

`score / label-blind representation`
→ `Roman Numeral specialist`
→ `Key specialist`
→ `Function specialist`
→ `bounded specialist evidence`
→ `st-guitar-harmonic-engine deterministic resolver`
→ `confidence / ambiguity / abstention policy`
→ authoritative harmonic result

No specialist may directly mutate engine state or become the authoritative resolver.

## Development-data boundary

Stage 2-A itself authorizes no new model fit. Any later specialist training stage must:

- use TRAIN only for fitting and hyperparameter/development work;
- use TRAIN-only grouped internal CV before another original VALIDATION evaluation;
- keep CALIBRATION and HOLDOUT sealed;
- remain label-blind on the feature side;
- preserve work-family leakage barriers;
- keep model scores explicitly non-probabilistic until a separately authorized calibration stage;
- keep all checkpoints and private target bodies outside Git.

## Failure isolation

Each specialist must have its own metric and PASS/HOLD result. A strong Key specialist must not hide a weak Roman Numeral specialist, and vice versa. Combined system evaluation is allowed only after the individual specialist gates are reported separately.

## Deferred tasks

Stage 2-A does not authorize:

- event-level v2 targets;
- `local_key` modeling;
- cadence/inversion/extension/etc. modeling from unsupported TAVERN targets;
- calibration;
- HOLDOUT access;
- production integration.

Those require separately reviewed data and contracts.
