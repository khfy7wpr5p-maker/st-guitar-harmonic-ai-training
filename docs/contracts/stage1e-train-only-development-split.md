# Stage 1-E — TRAIN-only internal development split/CV contract

Status: **PLANNED / NOT IMPLEMENTED / NOT AUTHORIZED**.

Stage 1-E defines the next architecture gate after Stage 1-D. It exists to prevent iterative event-level representation/model development from repeatedly optimizing against the already-frozen original VALIDATION partition.

This document does not create a split, materialize targets, train a model, change thresholds, or grant production authority.

## Input boundary

The only admissible source for Stage 1-E is the existing Stage 0-T TRAIN partition:

- TRAIN records: 487
- TRAIN work families: 18
- original VALIDATION: forbidden as an internal-development source
- CALIBRATION: forbidden
- HOLDOUT: forbidden

No record may be promoted into Stage 1-E from VALIDATION, CALIBRATION, HOLDOUT, or the Stage 1-D quarantine set merely to improve coverage.

## Grouping boundary

Internal development assignment must operate on work-family / direct-lineage groups, not independent rows.

Required invariants:

- every record from the same canonical work family stays in one internal group/fold;
- direct-lineage aliases from other corpora inherit the same internal group as their TAVERN source family;
- preserved A/B variants stay attached to their source record and may not be split across internal groups;
- augmentation is allowed only inside the internal training side of a development iteration and remains attached to the originating group;
- no feature, target, filename, annotation-source choice, or future model score may influence group assignment.

## Determinism and evidence

The implementation stage must choose and pin a deterministic grouped assignment procedure. Exact seed/fold counts are intentionally not invented in this planning contract; they must be derived and reviewed with evidence when Stage 1-E is implemented.

The implementation must emit repository-safe evidence containing at least:

- source TRAIN manifest digest;
- source work-family lineage digest;
- deterministic assignment algorithm/version;
- chosen seed or fold definition;
- internal group/fold counts;
- record counts per group/fold;
- proof of zero cross-group work-family overlap;
- proof of zero original VALIDATION/CALIBRATION/HOLDOUT access;
- canonical assignment-manifest SHA-256;
- authority fields proving that event-target materialization, model training promotion, and production authority were not implicitly granted.

Private target bodies and extracted corpus data remain outside Git.

## Stage 1-D interaction

Stage 1-D produced 557 event-alignment candidates and quarantined 137 records for event-level materialization. Stage 1-E does not convert those candidates into event-level teacher gold.

A later, separately reviewed Stage 1-F contract must define how an admitted Stage 1-D alignment candidate can be transformed into event-level training targets while preserving:

- the original human-selected A/B authority;
- `GOLD_VARIANT` set-valued semantics;
- exact source/hash provenance;
- deterministic event identity;
- fail-closed handling for unresolved or mismatched paths.

## Acceptance gate for implementation

When Stage 1-E is later implemented, the gate must fail closed unless all of the following are demonstrated:

- source is exactly the frozen original TRAIN partition;
- all 18 TRAIN work families are accounted for exactly once in the internal grouping definition;
- work-family overlap across development groups/folds is zero;
- direct-lineage alias overlap across development groups/folds is zero;
- original VALIDATION access count is zero;
- CALIBRATION access count is zero;
- HOLDOUT access count is zero;
- assignment is deterministic across reruns;
- assignment evidence is canonical and hash-pinned;
- no event targets are materialized by this gate;
- no model parameters are fit by this gate;
- no production authority is granted.

Until implementation and CI-reviewed evidence exist:

- `stage1e_status=PLANNED_NOT_IMPLEMENTED`
- `internal_development_split_materialized=false`
- `event_target_materialization_authorized=false`
- `event_level_model_training_authorized=false`
- `production_authority=false`
