# Stage 0-B / 0-C contracts

## Source manifests

A source is `READY` only when its immutable identity, three SHA-256 evidence hashes, license metadata, provenance and known issues are present. Missing hashes or unresolved licenses are fail-closed: the source remains `QUARANTINE` with an explicit reason.

ZIP contents are never trusted as source truth merely because they were extracted. Later ingestion code must validate extracted records against these contracts before promotion.

## Gold tiers

Supported tiers are `GOLD_CONSENSUS`, `GOLD_EXPERT`, `GOLD_VARIANT`, `SILVER_REVIEWED`, `SILVER_AUTO`, `UNLABELED_CLEAN`, and `QUARANTINE`.

Automatic/model-generated annotation cannot directly become teacher-gold. `AMBIGUOUS` and `ABSTAIN` are preserved adjudication outcomes rather than being silently forced into a single label.

Source labels are immutable evidence. Normalized ST labels will be added separately in Stage 0-G; normalization must never overwrite `raw_source_label`.
