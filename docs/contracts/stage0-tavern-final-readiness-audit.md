# Stage 0-U — TAVERN final pre-training readiness audit

Stage 0-U composes the completed Stage 0-Q/R/S/T summary contracts into one fail-closed pre-training gate. It does not replace the general Stage 0-H audit; it records whether the reviewed TAVERN subset is currently ready to become a training payload.

Verified readiness facts:
- 694 human-provenance teacher-gold records (`641 GOLD_EXPERT`, `53 GOLD_VARIANT`)
- 243 review records remain quarantined and are excluded
- 24 canonical work families are lineage-bound
- cross-corpus When-in-Rome/AugmentedNet aliases are bound to those families
- split seed `st-tavern-split-v1:12` is identity-only
- TRAIN 487 / VALIDATION 125 / CALIBRATION 41 / HOLDOUT 41
- all four partitions are non-empty
- calibration and holdout consist of teacher-gold metadata
- augmentation is TRAIN-only
- leakage gate is PASS at work-family level

Current real gate is **HOLD**, not PASS, because two prerequisites remain:
- `RAW_LABEL_REALIZATION_PENDING`: the selected TAVERN A/B raw label bytes must be reread from the pinned archive and verified against their Stage 0-Q SHA-256 anchors.
- `DETERMINISTIC_NORMALIZATION_PENDING`: those verified raw labels must be mapped through the reviewed TAVERN corpus adapter into `st-harmony-normalization-v1` without musical inference.

Therefore `training_authorized=false`. No model may train from Stage 0-U HOLD.

The validator fails closed on source/revision/digest/count/gold-distribution/split-distribution/seed/alias/augmentation or upstream-authority tampering. A future PASS is possible only when both raw-label realization and deterministic normalization are explicitly complete and all other gates remain unchanged.
