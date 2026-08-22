# Stage 0-Q — TAVERN teacher-gold materialization contract

## Purpose

Stage 0-Q converts only the 694 Stage 0-M-valid human decisions into final teacher-gold provenance metadata while keeping raw label bytes external and hash-bound. It does not normalize musical semantics, assign partitions, or authorize training.

## Pinned input

- TAVERN revision: `7cc65dc5365603a92376af50ac71491bea7a16ae`
- Stage 0-L comparison SHA-256: `b6f3e80c98acbdeac964ae47f568bf9a6c7eead6efbc221b47d74cdb56293db4`
- Validated human-decision artifact SHA-256: `0e53133bf150a101f1b55329c4c5741168fbe7b9ac9a748f221ec07fade1be4a`
- Validated decisions: `694`
- Normalization contract: `st-harmony-normalization-v1`

## Deterministic materialization

- `SELECT_A` → `GOLD_EXPERT` + `HUMAN_EXPERT`, selected source `A`.
- `SELECT_B` → `GOLD_EXPERT` + `HUMAN_EXPERT`, selected source `B`.
- `PRESERVE_VARIANTS` → `GOLD_VARIANT` + `HUMAN_VARIANT`, selected sources `A+B`.
- `CONFIRM_EQUIVALENT` → `GOLD_CONSENSUS` + `HUMAN_CONSENSUS` only when explicitly present as a human decision.
- `AMBIGUOUS` / `ABSTAIN` remain `QUARANTINE`.

The selected raw source label is represented by the exact upstream A/B SHA-256 anchor. Raw annotation text is not committed. `raw_source_label=None` in the metadata is therefore not evidence loss: the record carries `selected_raw_label_sha256` and `selected_sources` and is intentionally marked `HASH_BOUND_EXTERNAL_LABEL_PENDING`.

## Real result

- `GOLD_EXPERT`: 641
- `GOLD_VARIANT`: 53
- total materialized teacher-gold metadata records: 694
- external raw-label realization pending: 694

## Authority boundary

`gold_assignment_authorized=true` means the human-provenance gold tier itself is now fixed for these 694 records. It does **not** mean the records can train a model.

The following remain false:

- `partition_assignment_authorized`
- `training_authorized`
- every record's `training_eligible`

Before training, a deterministic TAVERN corpus adapter must reread the selected raw A/B label from the pinned archive, verify the selected SHA-256, preserve the raw source label, and construct `NormalizationRecord` under `st-harmony-normalization-v1` without musical inference.

The 203 PDF-capture-loss records and 40 schema-incompatible choices remain quarantined under Stage 0-O and are not inputs to this stage.
