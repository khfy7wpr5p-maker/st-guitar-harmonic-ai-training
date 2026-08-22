# Stage 1-B2 — Deterministic label-blind `**kern` feature schema

This stage resolves `DETERMINISTIC_FEATURE_SCHEMA_PENDING` without reading harmonic targets or starting a learned model.

Adapter version: `st-tavern-kern-bow-v1`.

For each already hash-bound score phrase, the adapter selects only declared `**kern` spines and creates a bounded sparse bag of source-syntax tokens:
- one `SPINE_COUNT::<n>` feature;
- literal interpretation features `INTERP::<token>` for `*...` tokens;
- barline occurrences are normalized to the single structural feature `BARLINE` so measure numbers do not become identity shortcuts;
- Humdrum null continuations become `NULL`;
- each whitespace-separated source data atom becomes `KERN_ATOM::<atom>` without pitch, duration, enharmonic, inversion, chord, cadence, or harmonic interpretation.

Global comments and local comment tokens are ignored. No harmonic labels, human decisions, partition names, work IDs, composer names, filenames, or target-derived vocabulary are input features. This prevents label-aware feature construction and obvious identity leakage.

The adapter is intentionally conservative. It does not claim that raw `**kern` surface atoms are the final best musical representation. It provides a deterministic first scientific input representation that can be replaced only by a separately versioned, reviewed adapter.

Security bounds reject excessive line count, spine count, cell-token size, feature cardinality, feature occurrence count, changed score hashes, changed score-input manifest, malformed ZIPs, and missing/ambiguous source structure.

Real pinned result across 694 reviewed score phrases:
- feature vocabulary: 6108 literal feature keys
- total feature occurrences: 133110
- `**kern` data atoms: 71709
- processed source rows: 51696
- interpretation tokens: 12710
- barline tokens: 13052
- null tokens: 34945
- spine counts: 521 two-spine, 84 three-spine, 89 four-spine phrases
- distinct features per record: min 24 / max 313
- feature occurrences per record: min 37 / max 1220
- feature manifest SHA-256: `184ea471894ff6cf376255d62e1f348c0878dc4c53939289b95fae40cb261126`

Feature records remain derived data outside Git; committed evidence contains only counts and digests.

Authority after this stage remains:
- `score_input_realization_complete=true`
- `deterministic_feature_schema_complete=true`
- `training_payload_manifest_complete=false`
- `model_training_started=false`
- `training_authorized=false`

The next safe step is to join feature hashes, normalized human targets, and the frozen work-family split into one read-only training payload manifest while preserving HOLDOUT isolation.
