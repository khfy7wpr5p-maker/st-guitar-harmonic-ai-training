# Stage 0-S — TAVERN reviewed-subset lineage closure

Stage 0-S binds every reviewed TAVERN work to the source-neutral canonical work family already established in Stage 0-J. The purpose is leakage prevention before any split.

Real reviewed subset:
- 694 reviewed records
- 24 active canonical work families
- 3 documented TAVERN works with no admitted reviewed records: `Beethoven/B071`, `Mozart/K025`, `Mozart/K179`

For every active work, `canonical_work_id == split_group_id`. Stage 0-J's direct source lineage aliases for When-in-Rome and AugmentedNet are retained. Any future admitted copy/converted derivative carrying one of those aliases must inherit the same split group and partition as the TAVERN family.

This stage does not claim byte identity between corpora. The lineage strength remains `DIRECT_SOURCE_LINEAGE`.

Fail closed on unknown work IDs, duplicate phrase keys, wrong validated-decision digest/count, unexpected active-family coverage, or duplicate canonical family IDs.

Authority remains:
- `partition_assignment_authorized=false`
- `training_authorized=false`
