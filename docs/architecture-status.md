# Current architecture status

This document is the current-state index for `st-guitar-harmonic-ai-training`. Historical stage contracts remain immutable evidence of the gate state that existed when each stage was introduced; use this file plus later completion contracts to determine current authority.

## Authority model

The repository trains specialist harmonic models only as bounded advisory evidence for `st-guitar-harmonic-engine`:

`teacher gold / dataset → specialist model → validated bounded evidence → deterministic engine resolver → confidence / ambiguity / abstention → authoritative harmonic result`

A learned model never becomes the authoritative harmonic resolver, never mutates engine state directly, and may not present an uncalibrated model score as a probability.

## Verified architecture chain

| Stage | Current architectural result | Authority consequence |
| --- | --- | --- |
| Stage 0-Q | 694 human-reviewed decisions materialized as teacher-gold provenance metadata | no training authority |
| Stage 0-R | reviewed TAVERN subset admitted with hash/license boundaries | dataset engineering only |
| Stage 0-S | 694 records bound to source-neutral work-family lineage groups | enables leakage-safe grouping |
| Stage 0-T | fixed split: TRAIN 487 / VALIDATION 125 / CALIBRATION 41 / HOLDOUT 41 | partition use becomes explicit |
| Stage 0-V | selected raw A/B label paths reread and hash-verified | resolves raw-label blocker |
| Stage 0-W | deterministic `st-harmony-normalization-v1` targets materialized | resolves normalization blocker |
| Stage 0-X | final TAVERN dataset-readiness blockers closed | dataset readiness PASS |
| Stage 1-A | bounded model contract and frozen offline-shadow thresholds | production remains forbidden |
| Stage 1-B1 | 694 score inputs resolved and hash-bound | score-input blocker closed |
| Stage 1-B2 | deterministic label-blind `**kern` feature representation | feature-schema blocker closed |
| Stage 1-B3 | leakage-safe 694-record training payload manifest | HOLDOUT/CALIBRATION fitting access forbidden |
| Stage 1-B4 | deterministic dependency-free `fieldwise-multinomial-nb-v1` implementation | model implementation blocker closed |
| Stage 1-B5 | final offline-training entry gate PASS | v1 `OFFLINE_EXPERIMENT_ONLY` training scope allowed |
| Stage 1-C | first official private whole-phrase fit completed; original VALIDATION result observed as HOLD | failed v1 checkpoint cannot be promoted; CALIBRATION/HOLDOUT remain sealed |
| Stage 1-D | source-derived event-alignment audit | event-level targets/training remain unauthorized |
| Stage 1-E | deterministic 3-fold TRAIN-only group plan implemented; event-level private materialization remains pending | no original VALIDATION/CALIBRATION/HOLDOUT access; no event-level training authority |
| Stage 2-A | first specialist wave frozen to Roman Numeral, Key, and Function | specialist architecture fixed; no automatic authority |
| Stage 2-B | exact private TRAIN-only specialist payload materialized: 487 records / 18 families / 3 folds | original VALIDATION/CALIBRATION/HOLDOUT remain outside iterative development |
| Stage 2-C | three independent specialist NB baselines evaluated by TRAIN-only grouped CV | Key shows learning signal; Function shows no gain over majority; Roman Numeral is zero; no promotion authority |
| Stage 2-D | TRAIN-only target-learnability audit implementation added; private audit pending | diagnose target-space sparsity before changing model/representation; no model fitting or non-TRAIN access |

## Stage 1-C first official v1 run

The exact first-run inputs were operationally hash-verified outside Git:

- 694 human-adjudicated decisions SHA-256 `0e53133bf150a101f1b55329c4c5741168fbe7b9ac9a748f221ec07fade1be4a`;
- pinned TAVERN ZIP SHA-256 `b95d85bb3f1e5c0f4ea6df772928d247243485abd93153f0550d6be2fba4fc63`;
- locked runtime Python `3.12.8`.

The first private attempt correctly stopped before fitting when four TRAIN `PRESERVE_VARIANTS` records exposed a source-provenance/model-target mismatch: distinct reviewed A/B source slots can normalize to the same `NormalizedSTLabel` while the model contract forbids duplicate acceptable targets.

Stage 1-C resolved this without changing human decisions, raw TAVERN evidence, the normalized-target manifest, split, or pinned private shard provenance. Private shards retain source-target slots while the model boundary uses `CANONICAL_NORMALIZED_UNIQUE_SET` semantics.

The rerun completed fitting and deterministic reverse-order reproduction. The operator-provided summary reports:

- `model_training_started=true`;
- `deterministic_rerun_match=true`;
- TRAIN 487 records / 500 source target slots / 496 effective model targets;
- VALIDATION 125 records / 154 source target slots / 154 effective model targets;
- exact normalized-label match `0.000`;
- variant-aware acceptable-set accuracy `0.000`;
- Roman-numeral component accuracy `0.000`;
- functional-component accuracy `0.056`;
- all four frozen validation thresholds FAIL;
- `validation_gate_status=HOLD`;
- `calibration_accessed=false`;
- `holdout_accessed=false`;
- `production_authority=false`;
- checkpoint SHA-256 reported as `fffffc65a29755cd61c055caf7118cce042579d20db18e191903ad4875308078`.

This remains an operationally observed HOLD rather than a byte-hash-bound final repository receipt for the exact `experiment-summary.json`. No threshold may be lowered and the v1 checkpoint may not be promoted while that HOLD stands.

## Stage 1-D / 1-E event-level boundary

Stage 1-D audited 694 reviewed records / 747 selected A/B target paths against TAVERN Joined carriers without treating Joined harmonic labels as authority. Pinned observations include:

- 600 selected paths with exact reciprocal-duration sequence;
- 147 mismatched or incomplete paths;
- 47 Joined harmonic label sequences token-exact to selected Encoder syntax;
- 700 not token-exact;
- 557 record-level event-alignment candidates;
- 519 expert candidates;
- 38 preserved-variant candidates;
- 137 quarantined records;
- 6,534 harmonic event paths in admitted alignment candidates.

Stage 1-E has a deterministic work-family plan over the exact 18 Stage 0-T TRAIN families:

- development seed `st-stage1e-grouped-cv-v1`;
- folds 3;
- work-family distribution 6 / 6 / 6;
- policy `SHA256_RANK_ROUND_ROBIN_IDENTITY_ONLY`;
- group-plan SHA-256 `ae15ed507247548907815f8ee1a5586f9fa2384a32d5102e887ddedff52e1a4c`;
- label-aware assignment false.

The separate event-level Stage 1-E private handoff remains pending. Stage 1-F event-target materialization therefore remains unauthorized.

## Stage 2-A / 2-B specialist data boundary

The whole-phrase v1 HOLD motivates decomposition rather than threshold relaxation. The first specialist wave is:

- `ROMAN_NUMERAL_SPECIALIST` → `roman_numeral`;
- `KEY_SPECIALIST` → `key`;
- `FUNCTION_SPECIALIST` → `phrase`.

`local_key`, `bass`, `inversion`, `chord_family`, `extension`, `suspension`, `alteration`, and `cadence` remain deferred because current TAVERN target support is absent or insufficient.

The Stage 2-B private run completed successfully under the exact source hashes while keeping semantic target parsing TRAIN-only. Bounded receipt values:

- private record manifest SHA-256 `cd39690a4be0355a3fbbac303395d4888a89d4204a81af11598e21a822c040cd`;
- TRAIN records 487;
- work families 18;
- fold record distribution 156 / 167 / 164;
- fold work-family distribution 6 / 6 / 6;
- source target slots 500;
- feature vocabulary 5,265;
- feature occurrences 94,065;
- Roman Numeral eligible records 487 / 487;
- Key eligible records 461 / 487;
- Function eligible records 478 / 487;
- `non_train_annotation_bodies_materialized=false`;
- `original_validation_target_access=false`;
- `calibration_target_access=false`;
- `holdout_target_access=false`;
- `model_training_started=false`;
- `production_authority=false`.

The full `specialist-train.private.json` remains external. The repository receipt is based on operator-provided summary values and does not claim an exact hash for the summary file itself.

## Stage 2-C observed TRAIN-only specialist diagnostic

Stage 2-C pins the exact Stage 2-B private record manifest and permits fitting only inside the three existing TRAIN development folds. Its baseline model family is `specialist-multinomial-nb-v1`, independently fitted for Roman Numeral, Key, and Function using frozen alpha candidates:

`0.25, 0.5, 1.0, 2.0, 4.0`

Candidate selection is frozen as:

`MAX_POOLED_ACCURACY_THEN_LOWEST_ALPHA`

The operator-provided private CV summary reports deterministic reproduction and the following pooled results:

| Specialist | Selected alpha | CV accuracy | Majority baseline | Delta |
| --- | ---: | ---: | ---: | ---: |
| Roman Numeral | 0.25 | 0.000000 | 0.000000 | 0.000000 |
| Key | 0.25 | 0.520607 | 0.143167 | +0.377440 |
| Function | 2.0 | 0.202929 | 0.202929 | 0.000000 |

Interpretation is intentionally bounded:

- Key has a clear TRAIN-internal learning signal above the fit-side majority baseline.
- Function provides no pooled gain over the majority baseline with the current phrase-level target and bag-of-words NB baseline.
- Roman Numeral obtains zero closed-set grouped-CV accuracy, and even its majority baseline is zero. This strongly motivates a target learnability audit before changing model capacity.

The reported run kept:

- `original_validation_target_access=false`;
- `calibration_target_access=false`;
- `holdout_target_access=false`;
- `full_train_final_fit_started=false`;
- `event_level_training_authorized=false`;
- `production_authority=false`;
- `calibrated_probability_output=false`;
- `deterministic_rerun_match=true`.

`evidence/stage2c_private_cv_receipt.v1.json` records only bounded operator-provided summary values. It explicitly does not claim the exact `stage2c-cv-summary.json` file SHA-256 is bound.

## Stage 2-D target-learnability boundary

The current TAVERN normalization adapter materializes Roman Numeral and Function as **whole-phrase JSON sequence strings**. A sequence such as a phrase's full harmonic path therefore becomes one closed-set class under the Stage 2-C baseline. If most complete sequences occur in only one work family/fold, a closed-set classifier cannot predict them in a held-out work family regardless of model capacity.

Stage 2-D tests that hypothesis using only the exact Stage 2-B TRAIN payload. For each specialist it measures:

- unique target count and unique-target-per-record ratio;
- singleton target count/fraction;
- target reuse factor;
- target presence across 1, 2, or all 3 folds;
- per-fold fit/evaluation target overlap;
- unseen held-out target occurrence rate;
- records with no acceptable target observed in the fit folds;
- closed-set oracle ceiling;
- privacy-safe sequence-length statistics for Roman Numeral and Function.

The audit writes no target values. It only parses Roman/Function canonical JSON arrays to count their lengths.

Stage 2-D authorizes **no model work**. All of these remain false:

- model fitting;
- model selection;
- full-TRAIN final fitting;
- original VALIDATION target access;
- CALIBRATION target access;
- HOLDOUT target access;
- event-level training authority;
- production authority.

The deterministic engine resolver remains authoritative.

## Scope separation

Three scopes must not be conflated:

1. **whole-phrase v1 experiment** — completed deterministically but HOLD on original VALIDATION; no promotion allowed.
2. **future event-level v2 development** — Stage 1-D/1-E groundwork exists, but event-target materialization/training remains unauthorized.
3. **specialist decomposition track** — Stage 2-B private TRAIN-only data is complete; Stage 2-C produced TRAIN-only diagnostic results; Stage 2-D diagnoses target learnability without fitting a model.

Original VALIDATION, CALIBRATION, HOLDOUT, and Stage 1-D quarantine remain outside iterative specialist development.

## Next safe work

After Stage 2-D code/CI merge, run the private target-learnability audit under Python 3.12.8:

`python -m scripts.run_stage2d_target_learnability_audit <specialist-train.private.json> <external-output-dir>`

Review only `stage2d-learnability-summary.json`.

The result determines the next specialist architecture choice:

- high unseen/singleton rates or a low closed-set oracle ceiling → redesign Roman/Function target representation before increasing model capacity;
- adequate target reuse/ceiling but weak Stage 2-C accuracy → improve label-blind features and/or model family;
- healthy learnability → preserve the target formulation and continue controlled specialist development.

Original VALIDATION must remain untouched during that choice. No full-TRAIN final specialist fit is authorized yet.

For the v1 evidence chain, the exact private `experiment-summary.json` should eventually be hash-bound before the observed HOLD is treated as a final repository evidence receipt.

## Repository security and artifact boundary

Raw corpora, archives, extracted private data, human target bodies, full private training payloads, model checkpoints/binaries, and private run artifacts remain outside Git. The repository contains only code, tests, contracts, manifests, hashes, immutable source revisions, split metadata, license/provenance records, transformation evidence, and bounded audit summaries.

Production authority remains outside this training repository and must continue to belong to the deterministic resolver/policy boundary of `st-guitar-harmonic-engine`.
