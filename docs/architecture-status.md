# Current architecture status

This document is the current-state index for `st-guitar-harmonic-ai-training`. Historical stage contracts remain immutable evidence of the gate state that existed when each stage was introduced; when a historical document says an earlier gate is HOLD, use this file plus later completion contracts to determine the current architecture state.

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
| Stage 1-C | sealed TRAIN/VALIDATION-only runner completed the first official private fit; validation result observed as HOLD | failed v1 checkpoint cannot be promoted; CALIBRATION/HOLDOUT remain sealed |
| Stage 1-D | source-derived event-alignment audit | event-level targets/training remain unauthorized |
| Stage 1-E | deterministic 3-fold TRAIN-only group plan implemented; private 487-record materialization pending | no original VALIDATION/CALIBRATION/HOLDOUT access; no event-level training authority |
| Stage 2-A | first specialist wave frozen to Roman Numeral, Key, and Function; unsupported targets deferred | architecture/dataset-engineering contract only; specialist training remains unauthorized |

## Stage 1-C first official v1 run

The exact first-run inputs were operationally hash-verified outside Git:

- 694 human-adjudicated decisions: SHA-256 `0e53133bf150a101f1b55329c4c5741168fbe7b9ac9a748f221ec07fade1be4a`;
- pinned TAVERN ZIP: SHA-256 `b95d85bb3f1e5c0f4ea6df772928d247243485abd93153f0550d6be2fba4fc63`;
- locked execution runtime: Python `3.12.8`.

The first private attempt correctly stopped before model fitting when four TRAIN `PRESERVE_VARIANTS` records exposed an integration mismatch: reviewed A/B provenance slots can deterministically normalize to the same `NormalizedSTLabel`, while the model contract forbids duplicate acceptable targets.

Stage 1-C resolved this without changing the human decisions, raw TAVERN evidence, normalized-target manifest, split, or pinned private shard provenance contract. Private shards preserve source-target slots and exact pinned digests. Model fitting and validation use `CANONICAL_NORMALIZED_UNIQUE_SET` semantics so canonically identical normalized labels collapse to one effective acceptable target while distinct variants remain distinct.

The rerun then completed model fitting and deterministic reverse-order reproduction. The operator-provided summary reports:

- `model_training_started=true`;
- `deterministic_rerun_match=true`;
- TRAIN: 487 records / 500 source target slots / 496 effective model targets;
- VALIDATION: 125 records / 154 source target slots / 154 effective model targets;
- exact normalized-label match: `0.000`;
- variant-aware acceptable-set accuracy: `0.000`;
- Roman-numeral component accuracy: `0.000`;
- functional-component accuracy: `0.056`;
- all four frozen validation thresholds: FAIL;
- `validation_gate_status=HOLD`;
- `calibration_accessed=false`;
- `holdout_accessed=false`;
- `production_authority=false`;
- checkpoint SHA-256 reported as `fffffc65a29755cd61c055caf7118cce042579d20db18e191903ad4875308078`.

This is an **operationally observed HOLD**, not yet a final repository evidence receipt: the exact `experiment-summary.json` bytes have not yet been imported/hash-bound into the public evidence chain. No threshold may be lowered and the v1 checkpoint may not be promoted while that HOLD stands.

## Stage 1-D evidence boundary

Stage 1-D audited 694 reviewed records / 747 selected A/B target paths against TAVERN Joined carriers without treating Joined harmonic labels as authority.

Observed pinned results:

- 600 selected paths have an exact reciprocal-duration sequence;
- 147 paths are mismatched or incomplete;
- only 47 Joined harmonic label sequences are token-exact to the selected Encoder syntax;
- 700 Joined harmonic label sequences are not token-exact;
- 557 record-level event-alignment candidates are admitted for future consideration;
- 519 are expert candidates;
- 38 are preserved-variant candidates with both selected paths aligned;
- 137 records remain quarantined for event-level materialization;
- 6,534 harmonic event paths are represented by admitted alignment candidates.

Joined files may carry source-derived event alignment evidence, but their embedded harmonic labels may not replace the human-selected Encoder targets.

## Stage 1-E current boundary

Stage 1-E has a deterministic repository-safe work-family plan over the exact 18 Stage 0-T TRAIN families:

- development seed: `st-stage1e-grouped-cv-v1`
- folds: 3
- work-family distribution: 6 / 6 / 6
- assignment policy `SHA256_RANK_ROUND_ROBIN_IDENTITY_ONLY`
- group-plan SHA-256: `ae15ed507247548907815f8ee1a5586f9fa2384a32d5102e887ddedff52e1a4c`
- label-aware assignment: false

The implementation also contains a fail-closed materializer for the private Stage 1-B payload. It emits only TRAIN identity/fold rows and rejects source partition drift, group leakage, duplicate phrase identities, HOLDOUT/CALIBRATION access escalation, and non-TRAIN families.

The public repository intentionally does not contain the private full 694-record training payload. Therefore the final 487-record fold materialization summary is still `PENDING_PRIVATE_PAYLOAD`.

This is the current event-level execution boundary:

`Stage 1-E group plan + materializer implementation`
→ **private Stage 1-B payload handoff required for real 487-record fold materialization**
→ Stage 1-F event-target materialization contract

## Stage 2-A specialist architecture boundary

The first whole-phrase v1 HOLD motivates decomposition rather than threshold relaxation. Stage 2-A therefore freezes the first specialist wave to targets actually supported by the current TAVERN normalization evidence:

- `ROMAN_NUMERAL_SPECIALIST` → `roman_numeral`; 747 normalized targets supported;
- `KEY_SPECIALIST` → `key`; 692 of 747 normalized targets contain an explicit key;
- `FUNCTION_SPECIALIST` → `phrase`; 739 of 747 normalized targets have a function spine.

`local_key` is deferred because only 1 of 747 normalized targets reports a key-change sequence. `bass`, `inversion`, `chord_family`, `extension`, `suspension`, `alteration`, and `cadence` are also deferred because the current TAVERN adapter materializes those fields as `null`.

Stage 2-A authorizes architecture and dataset engineering only. Specialist fitting remains closed until a later reviewed stage supplies a TRAIN-only grouped-CV development path. CALIBRATION, HOLDOUT, event-level training, and production authority remain closed.

## Scope separation

Three scopes must not be conflated:

1. **whole-phrase v1 experiment** — completed deterministically but currently HOLD on original VALIDATION; no promotion is allowed.
2. **future event-level v2 development** — Stage 1-D/1-E do not authorize event-target materialization or event-level model training.
3. **specialist decomposition track** — Stage 2-A defines bounded Roman Numeral, Key, and Function specialists but does not yet authorize fitting.

Original VALIDATION, CALIBRATION, HOLDOUT, and Stage 1-D quarantine remain outside iterative TRAIN-only development.

## Next safe work

For the v1 evidence chain, the exact private `experiment-summary.json` should be hash-bound before the observed HOLD is treated as a final repository evidence receipt.

For the specialist track, the next safe code stage is a **TRAIN-only specialist data/representation audit** that projects the existing TRAIN payload into separate Roman Numeral, Key, and Function tasks under the already-defined grouped internal CV policy. That stage must not read original VALIDATION, CALIBRATION, or HOLDOUT and must not start model fitting.

For the separate event-level track, the next operation remains private Stage 1-E record materialization using the hash-pinned Stage 1-B full payload:

`python scripts/materialize_stage1e_internal_cv.py <private-training-payload.json> --summary-only`

The complete assignment should remain private; only the bounded summary may be reviewed for commit.

## Repository security and artifact boundary

Raw corpora, archives, extracted private data, human target bodies, full private training payloads, model checkpoints/binaries, and run artifacts remain outside Git. The repository contains only code, tests, contracts, manifests, hashes, immutable source revisions, split metadata, license/provenance records, transformation evidence, and bounded audit summaries.

Production authority remains outside this training repository and must continue to belong to the deterministic resolver/policy boundary of `st-guitar-harmonic-engine`.
