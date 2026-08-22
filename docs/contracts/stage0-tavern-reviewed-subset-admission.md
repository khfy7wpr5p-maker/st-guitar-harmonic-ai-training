# Stage 0-R — TAVERN reviewed-subset admission

Stage 0-R admits only the 694 Stage 0-Q materialized records for **dataset engineering**. It does not admit the full TAVERN archive for training.

Pinned source evidence:
- revision `7cc65dc5365603a92376af50ac71491bea7a16ae`
- archive SHA-256 `b95d85bb3f1e5c0f4ea6df772928d247243485abd93153f0550d6be2fba4fc63`
- score inventory SHA-256 `7bdb7737e2f215bf1cda48e985279478d0b16751bbcca40c165179c5c85a5f7a`
- analysis inventory SHA-256 `04c327ed97774729f208b8767bd020e6106809a511576b08e853b8095a82907d`
- licence `CC-BY-SA-4.0`

Subset:
- admitted: 694
- excluded/quarantined: 243
- `GOLD_EXPERT`: 641
- `GOLD_VARIANT`: 53

The subset SourceManifest can be `READY` for acquisition/integrity because hashes and licence are resolved. This is intentionally narrower than training readiness. Selected raw label bytes are still external, semantic normalization is still pending, and work-family partitioning has not yet occurred.

Authority:
- admission scope: `DATASET_ENGINEERING_ONLY`
- `raw_label_realization_complete=false`
- `normalization_complete=false`
- `partition_assignment_authorized=false`
- `training_authorized=false`

The 203 PDF capture-loss records and 40 schema-incompatible choices remain outside the subset. When-in-Rome and AugmentedNet aliases must be bound to the same canonical work family before partitioning.
