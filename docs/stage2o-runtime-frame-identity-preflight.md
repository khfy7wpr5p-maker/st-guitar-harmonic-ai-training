# Stage 2-O — Cross-repository runtime-frame identity preflight

## Purpose

Stage 2-N added the engine-side stable `runtime_frame_id`. Stage 2-O independently
reproduces that exact identity algorithm inside the training repository and freezes
a cross-repository test vector before any private corpus alignment is attempted.

This stage is audit-only. It does not fit a model, materialize Function model
features, access non-TRAIN targets, or grant production authority.

## What is now solved

The training repository can independently reproduce the engine identity contract:

- engine Stage 2-N main SHA: `f631ec8c30df616b9d83d9269e56278742878d32`;
- identity schema: `st_guitar_harmonic_engine.runtime_frame_identity` v1.0;
- identity prefix: `st-rfi-v1:`;
- frozen vector: `st-rfi-v1:bf32699f237452f333a7f2132842a893ad5212728abc4840fbb43f1ea6b5cc43`.

This closes the risk that the two repositories silently hash the same frame in
different ways.

## What is still missing

Current TAVERN score tooling can identify immutable score bytes and inspect `**kern`
content, but the repository does not yet have a frozen, engine-equivalent source
materializer that proves all of the following exactly:

- engine-equivalent measure numbering;
- exact event onset;
- exact event duration after Humdrum null/sustain semantics;
- exact tie state;
- exact staff/voice mapping after spine splits/merges;
- exact non-silent `HarmonicFrame` segmentation;
- exact Stage2G Function event → runtime-frame join.

Therefore Function final training remains **HOLD**.

## Fail-closed rules

Stage 2-O rejects:

- nearest-frame matching;
- order-only matching;
- inferred onset or inferred duration;
- harmonic-label-assisted alignment;
- teacher-target-assisted alignment;
- next/future context;
- any non-TRAIN access.

`runtime_frame_id` remains a join key only and must not become a model feature.

## Next safe step

Stage 2-P should build and audit a bounded TRAIN-only `**kern` → engine runtime-frame
materializer. It must reproduce the engine `HarmonicFrame` contract from exact
source timing and note-state semantics. Only after that materializer passes should
a private Stage2G event-to-frame join audit run over the 1,854 Function events.

If exact source semantics cannot be reproduced for a path, that path stays
unmatched/quarantined. No recovery heuristic is allowed.
