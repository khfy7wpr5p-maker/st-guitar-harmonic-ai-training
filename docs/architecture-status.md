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
| Stage 1-C | sealed TRAIN/VALIDATION-only experiment runner | CALIBRATION/HOLDOUT remain sealed |
| Stage 1-D | source-derived event-alignment audit | event-level targets/training remain unauthorized |

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

Therefore Joined files may carry source-derived event alignment evidence, but their embedded harmonic labels may not replace the human-selected Encoder targets.

## Current gate boundaries

Two scopes must not be conflated:

1. **v1 whole-phrase offline experiment** — Stage 1-B5 permits only the sealed `OFFLINE_EXPERIMENT_ONLY` scope implemented by Stage 1-C. This is not production authority.
2. **future event-level v2 development** — Stage 1-D leaves event-target materialization and event-level model training unauthorized.

The original VALIDATION partition has already been observed diagnostically during model development. Repeated representation/model iteration against that frozen partition would weaken its value as an independent model-selection check. Event-level development must therefore establish a separate development loop using TRAIN only.

## Next safe stage

### Stage 1-E — TRAIN-only internal development split/CV

Status: **PLANNED / NOT IMPLEMENTED**.

Stage 1-E must:

- derive exclusively from the existing TRAIN partition: 487 records across 18 work families;
- group by work-family / direct-lineage identity, never by independent record-level random splitting;
- keep direct-lineage aliases in the same internal group;
- keep augmentation TRAIN-internal only and attached to its source group;
- produce a deterministic, reproducible assignment manifest with pinned digests;
- permit no original VALIDATION, CALIBRATION, or HOLDOUT access during iterative event-level representation/model work;
- authorize no event-target materialization by itself;
- authorize no production integration or engine mutation.

The implementation contract is documented in [`contracts/stage1e-train-only-development-split.md`](contracts/stage1e-train-only-development-split.md).

## Planned continuation after Stage 1-E

The safe continuation is expected to be:

`Stage 1-E TRAIN-only internal development split/CV`
→ `Stage 1-F separately reviewed event-target materialization`
→ `event-level representation/model v2 experimentation inside TRAIN-only development loop`
→ `frozen VALIDATION check`
→ `separately authorized CALIBRATION`
→ `one-way final HOLDOUT evaluation`
→ `bounded integration review for st-guitar-harmonic-engine`

Later stage names are architectural planning labels, not implementation or promotion authorization.

## Repository security and artifact boundary

Raw corpora, archives, extracted private data, human target bodies, model checkpoints/binaries, and run artifacts remain outside Git. The repository contains only code, tests, contracts, manifests, hashes, immutable source revisions, split metadata, license/provenance records, transformation evidence, and bounded audit summaries.

Production authority remains outside this training repository and must continue to belong to the deterministic resolver/policy boundary of `st-guitar-harmonic-engine`.
