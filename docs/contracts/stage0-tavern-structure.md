# Stage 0-H TAVERN structural / provenance gate

TAVERN is not admitted merely because its archive, licence and integrity hashes are valid. Structural provenance must also be explicit before any phrase can enter a teacher-gold sample manifest.

## Upstream documented contract

At pinned revision `7cc65dc5365603a92376af50ac71491bea7a16ae`, the upstream README documents 27 works (17 Beethoven, 10 Mozart), 1060 phrases, one score representation per phrase, and duplicate human analyses/joined representations for annotators A and B.

## Fail-closed rules

- `Encoder_A` and `Encoder_B` are human-variant candidates only; this gate does not itself promote them to `GOLD_VARIANT`.
- Any undocumented annotator folder/suffix, including observed `Encoder_C`, remains `QUARANTINE` until provenance is independently established.
- Joined files are derived score+analysis validation material and are not substituted for primary score or analysis evidence.
- Missing A/B counterparts, analysis without a corresponding score, score without documented analysis, or README-vs-observed phrase-count mismatch block blanket promotion.
- Work identity is established before split assignment. All 27 TAVERN work families remain `QUARANTINE` with `cross_corpus_dedup_status=PENDING` until downstream copies in When-in-Rome/AugmentedNet/other corpora are grouped into the same canonical family.
- No split is assigned while cross-corpus dedup is pending. `split_group_id` may be reserved deterministically, but TRAIN/VALIDATION/CALIBRATION/HOLDOUT assignment is withheld.
- These gates never authorize model training. Stage 0-H training remains fail-closed until the global dataset audit has no blockers.

## Acquired archive observation

The acquired archive bound to SHA-256 `b95d85bb3f1e5c0f4ea6df772928d247243485abd93153f0550d6be2fba4fc63` contains 1129 observed unique phrase keys versus the README's documented 1060, with 61 `Encoder_C` analysis files and incomplete A/B/score coverage. The exact observed summary is committed separately under `evidence/tavern/` so the discrepancy is auditable rather than silently normalized away.
