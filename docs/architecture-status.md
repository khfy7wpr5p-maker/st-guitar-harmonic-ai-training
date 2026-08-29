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
| Stage 2-D | private TRAIN-only target-learnability audit completed | Key target is structurally learnable; Function is partially sparse; Roman whole-phrase class target has zero closed-set ceiling |
| Stage 2-E | specialist target reformulation contract freezes separate Key / Function / Roman paths | target reformulation only; no model fitting or event-target authority |
| Stage 2-F | private TRAIN-only Function event-carrier audit completed and bounded receipt pinned | strong onset-carrier coverage supports onset events; duration evidence is insufficient for segments; no model authority |
| Stage 2-G | Function target shape frozen to `ONSET_EVENT`; TRAIN-only private materializer implemented | event-target materialization is bounded to admitted TRAIN carriers; model training and production authority remain closed |

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

The separate event-level Stage 1-E private handoff remains pending. Stage 1-F event-target materialization therefore remains unauthorized for the Roman Numeral track.

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

Interpretation remains bounded:

- Key has a clear TRAIN-internal learning signal above the fit-side majority baseline.
- Function provides no pooled gain over the majority baseline with the current phrase-level target and bag-of-words NB baseline.
- Roman Numeral obtains zero closed-set grouped-CV accuracy and zero majority baseline.

The reported run kept original VALIDATION, CALIBRATION, HOLDOUT, final full-TRAIN fit, event-level training, probability claims, and production authority closed.

## Stage 2-D observed target learnability

The current TAVERN normalization adapter materializes Roman Numeral and Function as whole-phrase JSON sequence strings. Stage 2-D measured whether those complete sequence strings are reusable across the existing TRAIN work-family folds.

The operator-provided private audit summary reports:

| Specialist | Unique targets | Singleton fraction | Target reuse | Pooled unseen rate | Closed-set oracle ceiling |
| --- | ---: | ---: | ---: | ---: | ---: |
| Key | 12 | 0.083333 | 38.416667 | 0.015184 | 0.984816 |
| Function | 101 | 0.564356 | 4.772277 | 0.271784 | 0.734310 |
| Roman Numeral | 432 | 0.909722 | 1.148148 | 1.000000 | 0.000000 |

Sequence-length observations are also structurally different:

- Key is scalar: mean/max = 1 / 1;
- Function sequence mean/max = 4.91 / 56;
- Roman sequence mean/max = 11.01 / 65.

This explains the Stage 2-C Roman result: every held-out Roman whole-phrase target occurrence is unseen in the fit folds, so the closed-set oracle ceiling is exactly zero. Increasing closed-set model capacity cannot fix that target formulation.

Function is less extreme but still has substantial whole-sequence sparsity and unseen held-out targets. Key has a healthy scalar target space and remains suitable for controlled classification research.

`evidence/stage2d_private_learnability_receipt.v1.json` stores bounded aggregate values only. It does not claim the exact private `stage2d-learnability-summary.json` file SHA-256 is bound.

## Stage 2-E specialist target reformulation

Stage 2-E freezes separate target decisions before any new fitting:

### Key

- current target: scalar `key` class;
- decision: `PRESERVE_SCALAR_TARGET`;
- next work requires a separate TRAIN-only model/feature gate;
- Stage 2-E itself authorizes no fit.

### Function

- current target: whole-phrase JSON function sequence treated as one class;
- decision: `RETIRE_WHOLE_PHRASE_CLASSIFICATION_TARGET`;
- intended replacement: aligned Function event/token sequence;
- prerequisite: `FUNCTION_EVENT_CARRIER_ALIGNMENT_AUDIT_REQUIRED`.

### Roman Numeral

- current target: whole-phrase JSON Roman sequence treated as one class;
- decision: `RETIRE_WHOLE_PHRASE_CLASSIFICATION_TARGET`;
- intended replacement: aligned harmonic event sequence;
- Stage 1-D event-alignment rows remain candidates, not target authority;
- prerequisite: private TRAIN-only Stage 1-E event materialization plus a later Stage 1-F contract.

Stage 1-D quarantined rows remain excluded. Stage 2-E does not reopen them. All Stage 2-E fitting, event-target, non-TRAIN, probability, and production authority switches remain false.

## Stage 2-F Function carrier boundary

Stage 2-F implemented the Function carrier prerequisite without materializing Function targets.

The private audit chain is:

`selected TRAIN Encoder **function row → same-row Encoder harmonic event → source-matched Joined harmonic carrier by exact reciprocal sequence`

The Joined harmonic **label text is not authority**. It is used only as an event carrier whose reciprocal sequence is compared with the hash-verified selected Encoder annotation, matching the structural principle established in Stage 1-D.

A source path becomes an onset-carrier candidate only when:

- it contains Function data events;
- every Function data event occurs on an Encoder harmonic-data row;
- the selected Encoder row width is stable;
- the complete Encoder harmonic reciprocal-event sequence is explicit and exactly matches the source-matched Joined carrier.

The completed private Stage 2-F audit is pinned by diagnostic manifest SHA-256 `968ea1afb3746d93702561c9472c01f3d6045866eb428447a20b14a22039885b`. Its bounded receipt reports:

- TRAIN records 487;
- Function-eligible records 478;
- onset-carrier candidate records 355;
- quarantined records 123;
- selected A/B source paths 500;
- Function-supported source targets 491;
- onset-carrier candidate source paths 366;
- quarantined source paths 125;
- Function events 2,406;
- Function events on harmonic rows 2,405;
- Function events without a harmonic row 1;
- explicit Function reciprocal events 865;
- comparable Function/harmonic reciprocal events 865;
- exact comparable reciprocal events 792;
- mismatches 73;
- fully duration-exact source paths 47;
- fold candidate-record distribution 97 / 130 / 128;
- fold work-family distribution 6 / 6 / 6.

The result supports deterministic onset attachment but not a duration-bearing segment target. Duration equality remains incomplete, so Stage 2-G freezes Function to `ONSET_EVENT`; `FUNCTION_SEGMENT`, inferred duration, and inferred segment boundaries remain rejected.

Stage 2-F itself kept event-target materialization, model fitting/model selection, final full-TRAIN fitting, event-level training, original VALIDATION target access, CALIBRATION target access, HOLDOUT target access, Stage 1-D quarantine reuse, and production authority false.

## Stage 2-G Function onset-event boundary

Stage 2-G freezes `FUNCTION_SPECIALIST_TARGET_SHAPE = ONSET_EVENT` and adds a private TRAIN-only materializer. The exact human-selected Encoder `**function` token is the target authority. Joined harmonic label text is never target authority and is used only for source-matched event-carrier structure evidence.

Admission is fail-closed:

- only the exact 487 original TRAIN identities are considered;
- Stage 1-E group-plan SHA-256 must remain `ae15ed507247548907815f8ee1a5586f9fa2384a32d5102e887ddedff52e1a4c`;
- Stage 2-B private-record manifest must remain `cd39690a4be0355a3fbbac303395d4888a89d4204a81af11598e21a822c040cd`;
- the Stage 2-F per-source diagnostic replay must reproduce `968ea1afb3746d93702561c9472c01f3d6045866eb428447a20b14a22039885b`;
- only records for which every selected A/B path remains an onset-carrier candidate may materialize;
- quarantined records cannot be partially recovered from one surviving variant path;
- A/B source provenance and development-fold identity are preserved.

Carrier event identity is deterministic and order-based. Stage 2-G does not invent score time, duration, segment end, or a missing Function token. It does not rewrite a source Function token.

Private output must remain outside Git. The operator handoff writes `function-onset-events.private.json` plus the shareable `function-onset-events-summary.json`, refuses overwrite, and rejects symlinked output paths. The summary contains aggregate counts, A/B event counts, variant provenance counts, and the private event manifest SHA-256 only; it omits Function token values and per-record event diagnostics.

After the Stage 2-G code merge, the private materialization must still be executed and its bounded summary reviewed before any Function event-level model-training contract is opened. The code stage does not itself authorize fitting.

Stage 2-G keeps these false:

- `original_validation_target_access`;
- `calibration_target_access`;
- `holdout_target_access`;
- `stage1d_quarantine_reuse_authorized`;
- `stage2f_quarantine_reuse_authorized`;
- `duration_inference_used`;
- `segment_boundary_inference_used`;
- `model_training_started`;
- `model_selection_started`;
- `full_train_final_fit_started`;
- `event_level_training_authorized`;
- `production_authority`.

`deterministic_resolver_remains_authoritative=true`.

## Scope separation

Three scopes must not be conflated:

1. **whole-phrase v1 experiment** — completed deterministically but HOLD on original VALIDATION; no promotion allowed.
2. **event-level development** — Roman Numeral remains on the Stage 1-E/1-F path; Function has a separate Stage 2-G onset-event materialization path, but no event-level training authority yet.
3. **specialist decomposition track** — Stage 2-B data is complete, Stage 2-C produced TRAIN-only diagnostics, Stage 2-D diagnosed target learnability, Stage 2-E froze target reformulation, Stage 2-F established Function onset-carrier feasibility, and Stage 2-G implements the bounded Function onset-event target materializer without fitting.

Original VALIDATION, CALIBRATION, HOLDOUT, Stage 1-D quarantine, and Stage 2-F quarantine remain outside iterative Function development.

## Next safe work

Run the Stage 2-G private materializer under Python 3.12.8 with the exact validated decision JSON and pinned TAVERN ZIP, writing only to an external directory. Review `function-onset-events-summary.json`; do not commit the private payload.

Only after that bounded summary is reviewed may a separate Function event-level TRAIN-only grouped-CV contract be considered. That later contract should freeze simple/majority baselines, a small deterministic/data-efficient model, per-event accuracy, macro metrics, work-family grouped CV, and unseen Function-token auditing before any fitting starts.

The Roman Numeral path remains separately blocked on private Stage 1-E event materialization + Stage 1-F. The Key path remains eligible for a separate TRAIN-only scalar feature/model gate. No Stage 2-G result can authorize production authority.

For the v1 evidence chain, the exact private `experiment-summary.json` should eventually be hash-bound before the observed HOLD is treated as a final repository evidence receipt.

## Repository security and artifact boundary

Raw corpora, archives, extracted private data, human target bodies, full private training payloads, model checkpoints/binaries, and private run artifacts remain outside Git. The repository contains only code, tests, contracts, manifests, hashes, immutable source revisions, split metadata, license/provenance records, transformation evidence, and bounded audit summaries.

Production authority remains outside this training repository and must continue to belong to the deterministic resolver/policy boundary of `st-guitar-harmonic-engine`.
