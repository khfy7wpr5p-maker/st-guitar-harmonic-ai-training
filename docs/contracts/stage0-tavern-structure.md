# Stage 0-I TAVERN structural/provenance gate

This gate converts the already integrity-pinned TAVERN archive into a deterministic structural audit. It does **not** admit samples to training.

## Pinned source policy

The adapter is valid only for TAVERN revision `7cc65dc5365603a92376af50ac71491bea7a16ae` **and** the previously admitted raw archive SHA-256 `b95d85bb3f1e5c0f4ea6df772928d247243485abd93153f0550d6be2fba4fc63`. A different revision or raw archive hash fails closed until integrity and structure are reviewed again. The pinned hash is regression-checked against the committed Stage 0-H integrity evidence.

The upstream README at this revision declares:

- 27 Beethoven/Mozart theme-and-variation works;
- 1060 phrases;
- one phrase score representation;
- two primary human analysis variants, annotators `A` and `B`;
- `Joined` files as analysis+score representations for those annotators.

The adapter treats those statements as source provenance, not as permission to invent or repair missing files.

## Parsing and provenance rules

- The raw archive SHA-256 must match the Stage 0-H evidence before structural parsing proceeds.
- The existing fail-closed ZIP security gate runs before any member is trusted as corpus structure.
- Work identity at this stage is source-local (`TAVERN::<composer>/<work>`). It is only a **work-family candidate**, not a final cross-corpus `canonical_work_id`.
- Phrase identity is derived from the documented variation/phrase positions in phrase-level filenames. Known `_V00_01_` score naming variants normalize to the same phrase key as `_00_01_` analysis filenames.
- Whole-work, fixed, original, interpreter or other `.krn` files under `Krn/` that do not match the phrase-score naming contract are support artifacts, not extra training phrases.
- Primary `Encoder_A` and `Encoder_B` files are documented human-variant provenance candidates. They are **not automatically promoted to teacher-gold** by this audit.
- Any primary annotator not documented by the pinned README (currently `Encoder_C` in the acquired archive) is reported and remains quarantined pending independent provenance evidence.
- `Joined` files are derived validation/alignment material. They never substitute for a missing primary analysis or missing phrase score.
- Duplicate primary roles for one work/variation/phrase fail closed rather than being arbitrarily selected.

## Admission blockers

The structural audit remains `HOLD` when declared and observed work/phrase counts disagree, undocumented annotators are present, primary A/B/score coverage is incomplete, or cross-corpus deduplication is unresolved.

Final TRAIN/VALIDATION/CALIBRATION/HOLDOUT assignment is forbidden at this stage. TAVERN is known to overlap downstream/meta corpora such as When-in-Rome and AugmentedNet, so final `canonical_work_id` and `split_group_id` fields remain null and every source-local work candidate remains `QUARANTINE` until cross-corpus work-family evidence is established.

The resulting structural evidence is summary-only and may be committed. Raw corpus bytes and phrase payloads remain outside Git.
