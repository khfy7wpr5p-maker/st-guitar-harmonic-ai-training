# Stage 2-Q — Exact runtime alignment coverage audit

Stage 2-Q is a TRAIN-only private coverage audit. It measures how many of the 1,854 Stage 2-G Function onset events across 363 materialized A/B source paths can be joined to an actual deterministic engine runtime frame by exact source-grounded identity.

## Inputs

- the frozen Stage 2-G private Function onset-event payload;
- the pinned TAVERN archive;
- the merged Stage 2-P exact `**kern` runtime-frame materializer;
- the Stage 2-N/2-O `runtime_frame_id` identity contract.

## Exact alignment rule

For every Stage 2-G phrase/source path, Stage 2-Q:

1. reopens the phrase-level `Krn/*_score.krn` source and materializes exact deterministic runtime frames with Stage 2-P;
2. reopens the corresponding Joined A/B carrier;
3. accepts Joined timing only when the file consists of static bounded `**kern` spines plus exactly one `**harm` spine;
4. runs one exact rhythmic clock across those spines using explicit reciprocals and null-sustain semantics;
5. uses the Stage 2-G `carrier_harmonic_event_index` only to select the already-frozen carrier event position;
6. verifies that Joined `**kern` runtime-frame primitives are exactly equal to the phrase score runtime-frame primitives;
7. joins a Function event only when its carrier position is exactly equal to an engine runtime-frame start in the same phrase-local measure.

The `**harm` label text is not interpreted. Only its explicit reciprocal participates in timing evidence.

A Function change that occurs in the middle of one unchanged deterministic runtime frame is intentionally **not** forced onto that frame. Such an event is reported as `CARRIER_NOT_RUNTIME_FRAME_START`.

## Fail-closed boundaries

Stage 2-Q does not use:

- nearest-frame matching;
- event-order-only matching;
- inferred onset or duration;
- future/next-frame context;
- teacher Function token values to construct alignment;
- Joined harmonic labels as harmonic authority;
- partial-alignment auto-admission;
- VALIDATION, CALIBRATION, or HOLDOUT target access.

Unsupported score/joined structures remain coverage failures instead of being guessed.

## Shareable output

The summary contains only aggregate counts and fixed provenance pins. It does not serialize `phrase_key`, `carrier_event_id`, `function_token`, or source annotation hashes.

Important fields are:

- `fully_exact_aligned_source_path_count`;
- `exact_aligned_event_count`;
- `exact_event_alignment_coverage`;
- `path_failure_reason_counts`;
- `event_failure_reason_counts`;
- `exact_stage2g_event_to_runtime_frame_alignment_complete`.

## Decision rule

There is no post-hoc threshold and no threshold lowering.

- All 363 source paths and all 1,854 events exact: `EXACT_ALIGNMENT_COMPLETE_REVIEW_NEXT`.
- Anything less: `HOLD_PARTIAL_EXACT_ALIGNMENT_COVERAGE`.

Even a complete Stage 2-Q result does not itself authorize model feature materialization or Function model training. A later stage must explicitly review the exact alignment evidence and freeze any newly authorized inference-safe event-local feature surface.
