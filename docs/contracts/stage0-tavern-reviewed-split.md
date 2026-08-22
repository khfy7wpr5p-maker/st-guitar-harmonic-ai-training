# Stage 0-T — TAVERN reviewed-subset leakage-safe split

Stage 0-T assigns partitions only after Stage 0-S work-family lineage closure.

Seed selection is deterministic and label-blind. Candidate seeds are `st-tavern-split-v1:<n>` in ascending integer order. The first seed whose 24 active canonical work families satisfy minimum family counts is selected:
- TRAIN >= 14 families
- VALIDATION >= 2
- CALIBRATION >= 2
- HOLDOUT >= 2

No class label, human decision, selected annotator, or sample count is consulted when choosing the seed. For the pinned 24 identities, the first satisfying seed is `st-tavern-split-v1:12`.

Real 694-record distribution:
- TRAIN: 487
- VALIDATION: 125
- CALIBRATION: 41
- HOLDOUT: 41

Every phrase inherits the partition of its canonical work-family `split_group_id`. When-in-Rome and AugmentedNet direct-lineage aliases are required to inherit that same partition if admitted later. Augmentation is TRAIN-only.

Stage 0-T authorizes the partition assignment itself (`partition_assignment_authorized=true`) but does not authorize model training. Raw selected labels still require hash-bound realization and deterministic normalization.
