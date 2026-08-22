# Stage 0-P — TAVERN gold-candidate mapping contract

## Purpose

Stage 0-P maps only the already validated Stage 0-M human decisions into **candidate** gold dispositions. It does not create final `GoldRecord` objects and does not authorize training.

## Pinned input

- TAVERN revision: `7cc65dc5365603a92376af50ac71491bea7a16ae`
- Stage 0-L comparison SHA-256: `b6f3e80c98acbdeac964ae47f568bf9a6c7eead6efbc221b47d74cdb56293db4`
- Validated human-decision artifact SHA-256: `0e53133bf150a101f1b55329c4c5741168fbe7b9ac9a748f221ec07fade1be4a`
- Validated decision count: `694`

The input artifact contains phrase keys, human decisions, and A/B hash anchors; it contains no raw annotation text.

## Deterministic mapping

- `SELECT_A` → `GOLD_EXPERT_CANDIDATE`, selected source `A`
- `SELECT_B` → `GOLD_EXPERT_CANDIDATE`, selected source `B`
- `PRESERVE_VARIANTS` → `GOLD_VARIANT_CANDIDATE`, selected sources `A+B`
- `CONFIRM_EQUIVALENT` → `GOLD_CONSENSUS_CANDIDATE` **only when that exact decision was explicitly made by the human reviewer**
- `AMBIGUOUS` → `QUARANTINE_AMBIGUOUS`
- `ABSTAIN` → `QUARANTINE_ABSTAIN`

The mapper never infers `CONFIRM_EQUIVALENT` from `BYTE_EXACT` or line-ending equivalence. The 40 Stage 0-O schema-incompatible equivalent-pair choices remain outside this input and therefore remain quarantined.

## Real Stage 0-P result

For the 694 validated human decisions:

- `SELECT_A`: 2
- `SELECT_B`: 639
- `PRESERVE_VARIANTS`: 53
- `GOLD_EXPERT_CANDIDATE`: 641
- `GOLD_VARIANT_CANDIDATE`: 53
- candidate quarantine: 0

These are candidate counts only. Stage 0-O still separately quarantines 203 PDF-capture-loss records and 40 schema-incompatible choices.

## Security boundary

The file-based mapper:

- rejects symlink input;
- requires a regular file;
- bounds the input to 1 MiB;
- verifies the exact pinned SHA-256 before accepting the artifact;
- validates corpus, revision, reviewer type, comparison digest, decision count, unique phrase keys, and hash shapes;
- outputs deterministic JSON with no raw annotation text.

The following remain `false`:

- `gold_assignment_authorized`
- `partition_assignment_authorized`
- `training_authorized`

A later stage must explicitly define and validate final `GoldRecord` construction, normalization binding, split safety, and audit gates before training can be considered.
