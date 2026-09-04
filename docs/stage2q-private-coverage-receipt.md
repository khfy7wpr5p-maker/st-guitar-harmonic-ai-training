# Stage 2-Q — Private aggregate coverage receipt

This receipt records the bounded aggregate result of the private TAVERN alignment audit after the Stage 2-Q corpus-reality correction.

The private audit used semantics equivalent to the merged Stage 2-Q v2 contract. The merged v2 runner has not yet been re-executed in the private Colab/Drive environment, so the receipt explicitly records `merged_stage2q_v2_runner_reexecution_completed=false` rather than overstating verification.

## Aggregate result

- 363 Stage 2-G materialized source paths were audited.
- 1,854 Function onset events were covered by the audit universe.
- 235 source paths were supported by the current exact Stage 2-P score materializer.
- 163 source paths also supported the exact Joined rhythmic clock.
- 139 source paths produced phrase-score and Joined runtime-frame primitives that were exactly equivalent.
- 137 source paths were fully exact event-to-frame aligned.
- 546 Function events were exactly aligned; 1,308 were not.
- Exact event coverage is `0.294498381877`.
- Exact source-path coverage is `0.37741046832`.

The remaining path outcomes are aggregate-only: 128 score-materializer unsupported paths, 72 Joined exact-timing unsupported paths, 24 score/Joined frame mismatches, and 2 event-level exact-join-incomplete paths.

## Safety decision

This is partial coverage, therefore the decision remains `HOLD_PARTIAL_EXACT_ALIGNMENT_COVERAGE`.

The 546 exact events are evidence that the identity bridge works on a meaningful safe subset, but partial auto-admission is forbidden. The receipt does not authorize event-local model feature materialization, Function model fitting, full-TRAIN fitting, non-TRAIN access, or production authority.

The next safe engineering direction is to expand exact source materialization for unsupported structural cases, especially dynamic Humdrum spine operations, while keeping mid-frame Function changes unaligned unless the deterministic runtime-frame contract itself gains an explicit source-grounded representation for them.
