# Stage 1-B1 — TAVERN score-input realization

This stage resolves `SCORE_INPUT_REALIZATION_PENDING` for the 694 reviewed records without building model features or starting training.

Each reviewed phrase key deterministically resolves exactly one TAVERN score phrase under `<composer>/<work>/Krn/`. Both historical filename forms `_VV_PP_score.krn` and `_VVV_PP_score.krn` are supported only through the existing Stage 0 score naming contract: the optional literal `V` before the two-digit variation index is accepted. No fuzzy filename matching is used.

Before any per-phrase input is admitted:
- the raw archive SHA-256 must equal the pinned TAVERN archive digest;
- the complete canonical TAVERN score inventory digest must equal `7bdb7737e2f215bf1cda48e985279478d0b16751bbcca40c165179c5c85a5f7a`;
- the validated 694-decision artifact digest must match the Stage 0-M pinned digest;
- every phrase key must be unique;
- every score phrase must resolve uniquely, remain within size bounds, decode as strict UTF-8, and contain exactly one exclusive-interpretation header with at least one `**kern` spine;
- ZIP path traversal, symlinks, duplicate members, corrupt archives, excessive member counts and excessive expanded size fail closed through the existing archive safety gate.

Real result:
- reviewed records / score inputs: 694
- complete TAVERN score inventory members: 1141
- selected score input bytes: 606576
- score-input manifest SHA-256: `de394ddcbbb18326b1fc91f162be9fa79eb515cd8e522dab915e79669d42075d`
- `score_input_realization_complete=true`

The committed evidence contains only source identities, counts and digests; score bodies remain outside Git.

This stage does **not** define ML features. `deterministic_feature_schema_complete=false`, `training_payload_manifest_complete=false`, and `training_authorized=false` remain mandatory. The next safe step is a deterministic, label-blind `**kern` feature schema.
