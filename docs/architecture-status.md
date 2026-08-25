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
| Stage 1-C | sealed TRAIN/VALIDATION-only experiment runner and private first-run handoff | CALIBRATION/HOLDOUT remain sealed; accepted private run still pending |
| Stage 1-D | source-derived event-alignment audit | event-level targets/training remain unauthorized |
| Stage 1-E | deterministic 3-fold TRAIN-only group plan implemented; private 487-record materialization pending | no original VALIDATION/CALIBRATION/HOLDOUT access; no event-level training authority |

## Stage 1-C current private-run boundary

The exact first-run inputs are now operationally available and hash-verified outside Git:

- 694 human-adjudicated decisions: SHA-256 `0e53133bf150a101f1b55329c4c5741168fbe7b9ac9a748f221ec07fade1be4a`;
- pinned TAVERN ZIP: SHA-256 `b95d85bb3f1e5c0f4ea6df772928d247243485abd93153f0550d6be2fba4fc63`;
- locked execution runtime: Python `3.12.8`.

The first private execution attempt correctly stopped before model fitting when four TRAIN `PRESERVE_VARIANTS` records exposed an integration mismatch: reviewed A/B provenance slots can deterministically normalize to the same `NormalizedSTLabel`, while the model contract forbids duplicate acceptable targets.

Stage 1-C resolves this without changing the human decisions, raw TAVERN evidence, normalized-target manifest, split, or pinned private shard provenance contract. Private shards continue to preserve source-target slots and exact pinned digests. After shard construction/verification, model fitting and validation use `CANONICAL_NORMALIZED_UNIQUE_SET` semantics so canonically identical normalized labels collapse to one effective acceptable target. Distinct variants remain distinct.

The experiment summary now separates source-target counts from effective model-target counts. This makes any collapse auditable without publishing private target bodies. No accepted checkpoint exists until the private run completes and passes the frozen validation gate.

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

Stage 1-E now has a deterministic repository-safe work-family plan over the exact 18 Stage 0-T TRAIN families:

- development seed: `st-stage1e-grouped-cv-v1`
- folds: 3
- work-family distribution: 6 / 6 / 6
- assignment policy: `SHA256_RANK_ROUND_ROBIN_IDENTITY_ONLY`
- group-plan SHA-256: `ae15ed507247548907815f8ee1a5586f9fa2384a32d5102e887ddedff52e1a4c`
- label-aware assignment: false

The implementation also contains a fail-closed materializer for the private Stage 1-B payload. It emits only TRAIN identity/fold rows and rejects source partition drift, group leakage, duplicate phrase identities, HOLDOUT/CALIBRATION access escalation, and non-TRAIN families.

The public repository intentionally does not contain the private full 694-record training payload. Therefore the final 487-record fold materialization summary is still `PENDING_PRIVATE_PAYLOAD`.

This is the current event-level execution boundary:

`Stage 1-E group plan + materializer implementation`
→ **private Stage 1-B payload handoff required for real 487-record fold materialization**
→ Stage 1-F event-target materialization contract

## Scope separation

Two scopes must not be conflated:

1. **v1 whole-phrase offline experiment** — Stage 1-B5 permits only the sealed `OFFLINE_EXPERIMENT_ONLY` scope implemented by Stage 1-C. The immediate v1 operation is the first accepted private TRAIN/VALIDATION run after the Stage 1-C integrity patch. This is not production authority.
2. **future event-level v2 development** — Stage 1-D/1-E do not authorize event-target materialization or event-level model training.

Original VALIDATION, CALIBRATION, HOLDOUT, and Stage 1-D quarantine remain outside the Stage 1-E iterative development loop.

## Next safe work

For whole-phrase v1, the next evidence-backed operation is to rerun the first official private Stage 1-C handoff with the exact pinned decisions/ZIP under Python `3.12.8`. The run must first reproduce the pinned TRAIN/VALIDATION shard digests, then fit TRAIN only and evaluate VALIDATION against the frozen thresholds. CALIBRATION and HOLDOUT remain closed.

For future event-level v2, the separate next operation remains private Stage 1-E record materialization using the hash-pinned Stage 1-B full payload:

`python scripts/materialize_stage1e_internal_cv.py <private-training-payload.json> --summary-only`

The complete assignment should remain private; only the bounded summary may be reviewed for commit.

After that event-level gate, the planned continuation is:

`Stage 1-F separately reviewed event-target materialization`
→ `event-level representation/model v2 experimentation inside TRAIN-only development loop`
→ `frozen VALIDATION check`
→ `separately authorized CALIBRATION`
→ `one-way final HOLDOUT evaluation`
→ `bounded integration review for st-guitar-harmonic-engine`

Later stage names remain architectural planning labels until separate CI-reviewed contracts authorize them.

## Repository security and artifact boundary

Raw corpora, archives, extracted private data, human target bodies, full private training payloads, model checkpoints/binaries, and run artifacts remain outside Git. The repository contains only code, tests, contracts, manifests, hashes, immutable source revisions, split metadata, license/provenance records, transformation evidence, and bounded audit summaries.

Production authority remains outside this training repository and must continue to belong to the deterministic resolver/policy boundary of `st-guitar-harmonic-engine`.
