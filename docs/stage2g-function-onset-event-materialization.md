# Stage 2-G — Function onset-event target materialization

Stage 2-G freezes the Function specialist target shape to `ONSET_EVENT` and adds a TRAIN-only private materializer. It does not train a model and does not grant model, validation, calibration, holdout, or production authority.

## Frozen source evidence

The materializer is pinned to:

- TAVERN revision `7cc65dc5365603a92376af50ac71491bea7a16ae`;
- validated human decisions SHA-256 `0e53133bf150a101f1b55329c4c5741168fbe7b9ac9a748f221ec07fade1be4a`;
- TAVERN archive SHA-256 `b95d85bb3f1e5c0f4ea6df772928d247243485abd93153f0550d6be2fba4fc63`;
- Stage 1-E group-plan SHA-256 `ae15ed507247548907815f8ee1a5586f9fa2384a32d5102e887ddedff52e1a4c`;
- Stage 2-B private-record manifest SHA-256 `cd39690a4be0355a3fbbac303395d4888a89d4204a81af11598e21a822c040cd`;
- Stage 2-F diagnostic manifest SHA-256 `968ea1afb3746d93702561c9472c01f3d6045866eb428447a20b14a22039885b`.

The bounded Stage 2-F receipt records 487 TRAIN records, 478 Function-eligible records, 355 onset-carrier candidate records, 123 quarantined records, 500 selected A/B source paths, 491 Function-supported source targets, 366 onset-carrier candidate source paths, and 125 quarantined source paths. Fold work-family distribution remains 6 / 6 / 6.

## Target authority

The only Function target authority is the exact human-selected Encoder `**function` token already present on a validated Encoder harmonic-data row. The Joined file contributes carrier/structure evidence only. Joined harmonic label text is never a Function target.

Stage 2-G does not:

- infer duration or segment boundaries;
- move a Function token to a nearest event;
- fill a missing Function token;
- reuse Stage 1-D or Stage 2-F quarantine;
- rewrite the source Function token;
- materialize any non-TRAIN annotation body.

Carrier identity is deterministic and order-based: phrase identity, A/B source provenance, selected annotation SHA-256, harmonic-event ordinal, and Function-event ordinal. No synthetic score time is introduced.

A record is materializable only when every selected A/B path for that record remains `FUNCTION_ONSET_CARRIER_CANDIDATE` under a deterministic Stage 2-F replay. The replayed per-path diagnostic manifest must equal the pinned Stage 2-F digest before private events may be emitted. A quarantined record cannot be partially materialized from a surviving variant path.

## Private artifact boundary

Run under the locked Python `3.12.8` runtime:

```bash
python scripts/materialize_stage2g_function_onset_events.py \
  /absolute/path/to/validated-decisions.json \
  /absolute/path/to/TAVERN.zip \
  /absolute/path/outside/repository/STAGE2G_FUNCTION_ONSET_EVENTS
```

The output directory must be outside the Git repository. Existing output files are never overwritten and symlinked output paths are rejected.

Expected private outputs:

- `function-onset-events.private.json` — private per-event rows including exact Function tokens and A/B provenance;
- `function-onset-events-summary.json` — shareable aggregate summary only.

The shareable summary contains counts, fold/work-family distributions, source A/B event counts, variant provenance counts, and the private event manifest SHA-256. It does not serialize Function token values, phrase identities, carrier event IDs, source annotation hashes, or per-record diagnostics.

## Authority after Stage 2-G code merge

Until the private Stage 2-G command is run and its bounded summary is reviewed, Stage 2-G is implementation-ready rather than evidence-complete. These remain false:

- `original_validation_target_access`;
- `calibration_target_access`;
- `holdout_target_access`;
- `stage1d_quarantine_reuse_authorized`;
- `stage2f_quarantine_reuse_authorized`;
- `duration_inference_used`;
- `segment_boundary_inference_used`;
- `model_training_started`;
- `model_selection_started`;
- `full_train_final_fit_started`;
- `event_level_training_authorized`;
- `production_authority`.

`deterministic_resolver_remains_authoritative=true`.

A successful Stage 2-G private materialization may justify a later, separate Function event-level TRAIN-only grouped-CV contract. It does not itself authorize that training stage. Roman Numeral and Key remain on their separate tracks.
