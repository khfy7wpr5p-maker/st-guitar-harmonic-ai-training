# Stage 2-P — Exact bounded `**kern` runtime-frame materializer

Stage 2-P implements the first training-side source adapter that can produce the
same primitive frame shape consumed by the deterministic harmony engine and hash it
with the Stage 2-N / Stage 2-O `runtime_frame_id` contract.

## Supported exact subset

The materializer is intentionally fail-closed. It accepts only bounded static
`**kern` spines with explicit `*staffN` metadata and exact reciprocal rhythm. It
supports ordinary and dotted reciprocals, tuplet reciprocals, extended `%`
reciprocals, breve/long/maxima zero notation, rests, Humdrum null sustain tokens,
multiple stops with equal duration, absolute `**kern` pitches/accidentals, and the
three engine tie states (`[`, `_`, `]`).

Each phrase is numbered locally from measure 1. Voice identity is the one-based
initial `**kern` spine ordinal. These policies are deterministic adapter semantics;
they are not learned fields and are not model features.

## Deliberately unsupported

The materializer rejects rather than guesses:

- spine split/join/exchange/add (`*^`, `*v`, `*x`, `*+`);
- partial spine termination;
- grace/appoggiatura materialization;
- missing `*staffN` metadata;
- early re-articulation while a prior duration remains;
- null tokens with no sustaining event/rest;
- mixed-duration multiple stops;
- ambiguous tie markings;
- malformed/implicit rhythm or pitch information.

This boundary is deliberate. Existing review rendering code is not treated as an
engine-equivalent timing parser.

## Timing algorithm

At each data record the adapter maintains an exact remaining duration per spine.
A non-null token may start only when that spine has zero remaining duration. A null
`.` token is legal only while the prior note/rest is still sounding. The next
Humdrum event time advances by the minimum positive remaining duration. Arithmetic
uses exact rational numbers only.

Within each phrase-local measure, note onsets and ends define maximal intervals of
constant active pitched notes. Silent intervals are omitted. Each non-silent
interval becomes an engine-frame primitive and receives the Stage 2-N
source-scoped `runtime_frame_id`.

## Safety

`runtime_frame_id` remains a join key, never a model feature. No Function/Roman/Key
label, teacher target, harmonic label, future context, inferred onset, inferred
duration, model score, non-TRAIN target, or production authority is used.

Function final training therefore remains **HOLD**.

## Next step

Stage 2-Q should run this materializer against the exact TRAIN score paths used by
the 363 Stage 2-G materializable source paths and report supported/quarantined
coverage without exposing private score/event bodies. Any unsupported path remains
quarantined. Only the exact supported subset may proceed to the private
Stage2G-event → runtime-frame join audit.
