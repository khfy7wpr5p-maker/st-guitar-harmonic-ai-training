# Stage 1-E acceptance checklist

Stage 1-E is acceptable for merge only if CI proves all repository checks green and the implementation preserves these invariants:

- exact Stage 0-T TRAIN family set: 18;
- deterministic three-fold identity-only group plan: 6 / 6 / 6;
- pinned group-plan digest unchanged;
- private materializer emits TRAIN identities only;
- source partition distribution remains 487 / 125 / 41 / 41;
- no original VALIDATION, CALIBRATION, HOLDOUT, or quarantine access is enabled;
- duplicate phrase identities and cross-partition split groups fail closed;
- output contains no target bodies, feature hashes, score hashes, or model outputs;
- event-target materialization remains unauthorized;
- Stage 1-E does not fit model parameters;
- production authority remains false.

The real 487-record materialization is not a public-repository merge requirement because its source payload is intentionally private. That operation is a separate private execution handoff after this code/contract gate passes.
