# Stage 0-J TAVERN cross-corpus lineage contract

Stage 0-J resolves the known **work-family identity** overlap between TAVERN, When-in-Rome, and AugmentedNet without authorizing phrase admission, final partitions, or model training.

## Pinned external evidence

The mapping is reviewed against immutable upstream revisions:

- TAVERN: `7cc65dc5365603a92376af50ac71491bea7a16ae`
- When-in-Rome: `1c61fe41b8c2910296d7d2bcbf6476c7c1f2fe35`
- AugmentedNet: `46d3475651346fd9053db29bc2bfb7943a869b74`

At the pinned When-in-Rome revision, the README explicitly identifies the 27 Beethoven/Mozart keyboard variation sets in `Corpus/Variations_and_Grounds` as conversions **from the TAVERN project**. The same revision exposes corresponding work directories such as `WoO_63`, `Op34`, and Mozart `K...` catalogue entries.

At the pinned AugmentedNet revision, `AugmentedNet/data/tavern.py` defines TAVERN-specific records that pair When-in-Rome TAVERN analyses with TAVERN score paths. This is direct source-lineage evidence, not filename-similarity inference.

## Identity rules

- The exact 27 Stage 0-I source-local TAVERN works must be present; missing, unexpected, duplicated, pre-assigned, or non-quarantined work summaries fail closed.
- Each source-local TAVERN work maps to one source-neutral `canonical_work_id` and the same `split_group_id`.
- The lineage record retains explicit aliases for TAVERN, When-in-Rome, and both AugmentedNet A/B record variants.
- These aliases identify one musical work family. They must never be counted as independent works across corpora.
- The mapping does not assert byte identity between converted formats or corrections. `DIRECT_SOURCE_LINEAGE` means the downstream source explicitly declares or encodes derivation from TAVERN.

## Still forbidden

Stage 0-J does **not** authorize TRAIN/VALIDATION/CALIBRATION/HOLDOUT assignment. The Stage 0-I phrase-structure mismatch, incomplete primary score/A/B coverage, undocumented Encoder_C provenance, and teacher-gold adjudication remain unresolved.

Therefore:

- `partition_assignment_authorized = false`
- `training_authorized = false`
- no raw corpus or downstream copy is committed to Git
- no downstream/meta-corpus alias may be admitted as an independent example

A later stage may assign partitions only after phrase eligibility and teacher-gold policy are deterministic and reviewed. Any such partitioning must use the Stage 0-J `split_group_id`, so all known TAVERN-derived copies remain in the same partition.
