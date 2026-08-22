# Stage 1-B3 — Leakage-safe training payload manifest

This stage resolves `TRAINING_PAYLOAD_MANIFEST_PENDING` by joining only already-pinned evidence: deterministic score features, normalized human-valid target sets, and the Stage 0-T work-family split. It does not train a model.

Each of the 694 payload records binds:
- `phrase_key`
- source/canonical work identity and `split_group_id`
- frozen partition
- `GOLD_EXPERT` or `GOLD_VARIANT`
- original human decision type
- score SHA-256
- deterministic feature SHA-256
- one or two selected target anchors containing source, raw-label SHA-256 and normalized-label SHA-256.

`PRESERVE_VARIANTS` records must contain both A and B targets. They are never collapsed to one arbitrary label. `SELECT_A` and `SELECT_B` records must contain exactly the corresponding single selected target.

Leakage/usage boundaries are explicit:
- TRAIN: parameter fitting may use target bodies.
- VALIDATION: model selection/evaluation only; not parameter fitting.
- CALIBRATION: later confidence calibration only; not parameter fitting.
- HOLDOUT: not available to fitting, model selection or threshold tuning.
- augmentation remains TRAIN-only.
- every `split_group_id` must occur in exactly one partition.
- cross-corpus aliases must inherit the same work-family partition.

Real pinned payload:
- records: 694
- selected human-valid targets: 747
- gold tiers: 641 `GOLD_EXPERT`, 53 `GOLD_VARIANT`
- partitions: TRAIN 487 / VALIDATION 125 / CALIBRATION 41 / HOLDOUT 41
- feature manifest: `184ea471894ff6cf376255d62e1f348c0878dc4c53939289b95fae40cb261126`
- normalized target manifest: `195ec1ce2193f8560043a94f3ea99c8db69b830fff6e60313c88565714450a4c`
- payload manifest: `79272bbe51d8e850a6b77ca26aa1c7eafb4b728f5b3d25d60a1e62332616e27a`

The full derived payload remains an external/local build artifact. Git stores only code, contracts, tests and digest/count evidence.

Authority remains fail-closed:
- `training_payload_manifest_complete=true`
- `model_implementation_complete=false`
- `model_training_started=false`
- `training_authorized=false`
- `production_authority=false`

The remaining Stage 1-B entry blocker is a bounded deterministic first model implementation plus its execution/checkpoint policy. Training may begin only after that implementation is separately reviewed, CI-PASSed and an entry gate explicitly authorizes **offline experiment only**.
