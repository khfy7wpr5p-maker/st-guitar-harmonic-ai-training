# Stage 0-D / 0-E / 0-F contracts

## Canonical work identity

Every record carries `canonical_work_id`, `edition_id`, `duplicate_cluster_id`, `derivation_parent_id`, and `split_group_id`. Repository copies, editions, format conversions, transpositions, and fragments must remain linkable to one work-family before split assignment.

## Cross-corpus deduplication

Deduplication never trusts filenames alone. Evidence combines normalized metadata with deterministic symbolic-content fingerprints. Exact symbolic matches are sufficient evidence for duplicate review even when metadata differs. Near-duplicate admission requires both matching metadata identity and symbolic similarity above the configured threshold.

Transposition-derived views must use transposition-invariant symbolic tokens before fingerprinting so that augmentation or alternate keys do not masquerade as independent works.

## Leakage-safe split

Split assignment is deterministic at `split_group_id` level. The validator rejects a canonical work, duplicate cluster, split group, or known derivation parent/child pair that spans partitions.

Allowed partitions are `TRAIN`, `VALIDATION`, `CALIBRATION`, `HOLDOUT`, `EXTERNAL_HOLDOUT`, and `QUARANTINE`.

Training augmentation is allowed only for `TRAIN`. A dedicated access guard rejects training-pipeline label access for every non-TRAIN partition, including VALIDATION, CALIBRATION, HOLDOUT, and EXTERNAL_HOLDOUT.

The required order is always: establish identity/dedup groups → assign split → augment TRAIN only.
