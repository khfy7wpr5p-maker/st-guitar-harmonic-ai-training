# Stage 2-K — Local harmonic context feasibility audit

Stage 2-K is an audit-only TRAIN stage after the Stage 2-J grouped-CV HOLD. It does not fit a model and does not authorize feature materialization.

The audit re-opens only the pinned TAVERN archive paths already represented by the frozen Stage 2-G materialized Function events. Every annotation body is verified against the Stage 2-G `source_annotation_sha256`, so no new source path or quarantined record is admitted.

For each Stage 2-G carrier it inspects the existing Encoder harmonic spine and measures aggregate availability of the current carrier harmonic token plus the immediately previous and next harmonic data events. Tokens and event identities are never written to the shareable summary.

This is only a structural feasibility result. The Encoder harmonic tokens are human-selected source annotations; Stage 2-K does **not** establish that equivalent features are available at inference time. Therefore current/previous/next harmonic tokens remain unauthorized as model features until a separate inference-safe feature-source contract is approved.

VALIDATION, CALIBRATION, and HOLDOUT remain closed. No duration, segment boundary, Function token, onset value, or joined harmonic label is inferred or rewritten. Production authority remains false and the deterministic resolver remains authoritative.
