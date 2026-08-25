# Stage 1-E — TRAIN-only internal development split/CV contract

Status: **IMPLEMENTED GROUP PLAN / PRIVATE RECORD MATERIALIZATION PENDING / NO MODEL TRAINING AUTHORITY**.

Stage 1-E prevents iterative event-level representation/model development from repeatedly optimizing against the already-frozen original VALIDATION partition. It introduces a deterministic identity-only grouped CV plan over the Stage 0-T TRAIN work families and a fail-closed private materialization path for the 487 TRAIN records.

This stage does not materialize event targets, fit model parameters, change thresholds, open CALIBRATION/HOLDOUT, or grant production authority.

## Input boundary

The only admissible record source is the frozen Stage 1-B training payload whose partition identity is inherited from Stage 0-T:

- source payload manifest SHA-256: `79272bbe51d8e850a6b77ca26aa1c7eafb4b728f5b3d25d60a1e62332616e27a`
- TRAIN: 487 records / 18 work families
- original VALIDATION: 125 records / forbidden for Stage 1-E development
- CALIBRATION: 41 records / forbidden
- HOLDOUT: 41 records / forbidden
- Stage 1-D quarantine: forbidden

The materializer reads the complete private payload only to verify the frozen partition boundary and emits Stage 1-E assignments for TRAIN records only. It never copies target sets, feature hashes, score hashes, or model outputs into the Stage 1-E assignment artifact.

## Deterministic grouped assignment

The repository-safe group plan is derived from the exact 18 Stage 0-T TRAIN canonical work-family identities.

Pinned definition:

- development seed: `st-stage1e-grouped-cv-v1`
- folds: `3`
- assignment policy: `SHA256_RANK_ROUND_ROBIN_IDENTITY_ONLY`
- group count: `18`
- groups per fold: `6 / 6 / 6`
- group-plan manifest SHA-256: `ae15ed507247548907815f8ee1a5586f9fa2384a32d5102e887ddedff52e1a4c`

The algorithm ranks each TRAIN `split_group_id` by SHA-256 of `development_seed + U+001F + split_group_id`, then assigns the ranked identities round-robin across three folds. Labels, targets, selected annotator, record counts, filenames, features, and model scores do not influence assignment.

Every record in one canonical work family therefore remains in one development fold. Direct-lineage aliases must inherit the same fold through the existing split-group identity.

## Private record materialization

`st_harmonic_training.stage1e_internal_cv` validates the private full Stage 1-B payload and fails closed unless:

- source corpus/revision and payload digest are pinned;
- the original partition distribution remains exactly TRAIN 487 / VALIDATION 125 / CALIBRATION 41 / HOLDOUT 41;
- HOLDOUT label access for training/model selection remains false;
- CALIBRATION label access for parameter fitting remains false;
- augmentation remains TRAIN-only;
- every split group remains in exactly one original partition;
- the Stage 1-E eligible set is exactly the 18 Stage 0-T TRAIN families and 487 TRAIN records;
- canonical work identity equals split-group identity;
- phrase identities are unique;
- no original VALIDATION/CALIBRATION/HOLDOUT record is emitted.

The private materialized assignment contains only:

- `phrase_key`
- `canonical_work_id`
- `split_group_id`
- `development_fold`

The complete record-level assignment remains external/private. Only a bounded summary may be committed after private execution.

## Repository-safe evidence

`evidence/stage1e_group_plan_summary.v1.json` pins the public group-level plan and authority boundary. Its current record materialization state is:

- `record_materialization_status=PENDING_PRIVATE_PAYLOAD`

This is not a failure of the grouping implementation. It records that the private 694-record training payload body is intentionally not stored in this public repository, so the final 487-record fold-count summary must be produced in the approved private execution environment.

## Stage 1-D interaction

Stage 1-D admitted 557 event-alignment candidates and quarantined 137 records. Stage 1-E does not convert any Stage 1-D candidate into event-level teacher gold.

Stage 1-F must remain separately reviewed and must preserve:

- original human-selected A/B authority;
- `GOLD_VARIANT` set-valued semantics;
- source/hash provenance;
- deterministic event identity;
- quarantine for unresolved or mismatched alignment paths.

## Current authority state

After implementation and CI PASS, Stage 1-E may authorize only the deterministic TRAIN-only development grouping/materialization operation.

It does **not** authorize event-level training or production:

- `original_validation_access=false`
- `calibration_access=false`
- `holdout_access=false`
- `quarantine_access=false`
- `event_target_materialization_authorized=false`
- `model_training_started=false`
- `training_authorized=false`
- `production_authority=false`

The pre-existing Stage 1-B5 v1 `OFFLINE_EXPERIMENT_ONLY` authority is a separate scope and is not expanded by Stage 1-E.
