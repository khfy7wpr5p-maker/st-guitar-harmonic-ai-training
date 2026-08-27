# Stage 2-F — Function event-carrier alignment audit

## Purpose

Stage 2-D showed that the current whole-phrase Function sequence-as-class target is not a suitable final formulation. Stage 2-E therefore retired that target and required a separate Function carrier-alignment audit before any event/segment target can be materialized.

Stage 2-F answers only this question:

> Can the human-selected TRAIN-only `**function` tokens be mapped deterministically to score-side event carriers without using Joined harmonic labels as target authority?

It does not train a model and does not create Function event targets.

## Source boundary

The private audit uses only:

- the exact 694 human-decision artifact;
- the exact pinned TAVERN ZIP;
- the fixed Stage 0-T TRAIN identity set (487 records / 18 work families);
- the existing Stage 1-E three-fold family plan.

The 694 decision JSON may be hash-verified and parsed as metadata, but raw annotation bodies are opened only after the TRAIN identity map is fixed. Original VALIDATION, CALIBRATION, and HOLDOUT annotation bodies are not materialized.

## Carrier chain

For each human-selected TRAIN A/B source path:

1. read the selected Encoder annotation and hash-check it against the human decision artifact;
2. locate the single `**harm` or `**chords` spine and optional single `**function` spine;
3. map each Function data token to the harmonic data event on the same Encoder row;
4. independently map the Encoder harmonic-event reciprocal sequence to the source-matched Joined carrier used by Stage 1-D;
5. admit an onset-carrier candidate only when the complete Encoder↔Joined harmonic reciprocal sequence is exact, row width is stable, and no Function token occurs without a harmonic row carrier.

Joined harmonic label text is never treated as teacher-gold or as a Function target. Only carrier structure / reciprocal sequencing is used.

## Duration interpretation

A Function token may describe a span wider than one harmonic event. Therefore Stage 2-F does **not** require its explicit reciprocal duration to equal the harmonic event reciprocal in order to admit an onset carrier.

Instead it reports a separate duration-exact diagnostic:

- all Function tokens on the path have explicit reciprocals;
- each is comparable with its same-row harmonic reciprocal;
- every comparable reciprocal is equal.

This diagnostic decides a later target-shape question: event label vs duration-bearing segment. Stage 2-F itself cannot make that target-shape decision.

## Output boundary

The operator-visible artifact is only:

`stage2f-function-alignment-summary.json`

The summary may contain aggregate counts, fold distributions, source hashes, policy pins, and a deterministic hash of private per-path diagnostics. It must not serialize:

- Function target values;
- harmonic label values;
- per-record diagnostics;
- event-index mappings;
- score feature vectors;
- checkpoints.

## Frozen authority

Stage 2-F keeps all of the following false:

- target-shape decision authority;
- event-target materialization;
- model fitting / model selection;
- full-TRAIN final fitting;
- event-level training;
- original VALIDATION target access;
- CALIBRATION target access;
- HOLDOUT target access;
- Stage 1-D quarantine reuse;
- production authority.

The deterministic `st-guitar-harmonic-engine` resolver remains authoritative.

## Next gate

After the private audit, only the aggregate summary is reviewed.

- Strong onset-carrier coverage with duration equality → Function may proceed toward an event-level target contract.
- Strong onset-carrier coverage but weak duration equality → Function likely needs a duration-bearing segment formulation.
- Weak onset-carrier coverage → quarantine / carrier redesign is required before any Function target materialization.

No later gate may infer a PASS without reviewing the actual private Stage 2-F summary.
