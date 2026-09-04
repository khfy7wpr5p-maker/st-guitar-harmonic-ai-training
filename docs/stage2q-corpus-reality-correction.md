# Stage 2-Q — Corpus-reality correction v2

The first Stage 2-Q implementation was deliberately narrow and passed CI, but private TAVERN inspection showed that its Joined-file assumptions did not match the frozen corpus. The real Joined files carry an extra `**function` spine and do not repeat the phrase score's explicit `*staffN` declarations.

This correction changes only source parsing required to measure exact alignment coverage. It does not relax the Function model HOLD.

## Corrected source contract

For each frozen Stage 2-G TRAIN source path, v2 requires:

- the phrase score to remain inside the exact Stage 2-P static `**kern` subset;
- the Joined source to contain bounded static `**kern`, exactly one `**harm`, and at most one `**function` spine;
- the Joined `**kern` spine count to equal the phrase score `**kern` spine count;
- staff identity to come from the phrase score's explicit `*staffN` mapping by `**kern` ordinal;
- any explicit Joined `*staffN` to agree with that score mapping;
- `**kern` and `**harm` reciprocals/null tokens to share one exact rational rhythmic clock;
- a `**function` data token, when present, to occur only on a row with a harmonic carrier data token.

The `**function` value is never parsed, serialized, used as timing evidence, or used to choose a runtime frame. The `**harm` label body is likewise not harmonic authority; only its explicit reciprocal is used as source-grounded timing evidence.

## Exact join rule

Joined `**kern` frames must be exactly equivalent to the phrase score frames after canonicalization. A Stage 2-G event is aligned only when its already-frozen `carrier_harmonic_event_index` resolves to the exact start of one deterministic runtime frame in the same phrase-local measure.

No nearest-frame matching, order-only fallback, inferred onset/duration, future context, label-assisted recovery, or partial auto-admission is allowed. Multiple Function events resolving to one runtime frame are rejected from exact one-event-per-frame coverage.

## Private corpus reality

The correction is intended to measure reality, not force a PASS. Unsupported dynamic spine operations, grace-note cases, score/Joined spine-count differences, malformed null-sustain cases, and Function changes inside an unchanged deterministic frame remain explicit coverage blockers.

The shareable result is aggregate-only. Private phrase IDs, Function tokens, carrier IDs, and annotation hashes are not serialized.

## Decision

Stage 2-Q remains audit-only. Complete exact coverage may advance only to a separate review stage. Partial exact coverage remains `HOLD_PARTIAL_EXACT_ALIGNMENT_COVERAGE`; it does not authorize training on the partial subset and does not permit threshold lowering.
