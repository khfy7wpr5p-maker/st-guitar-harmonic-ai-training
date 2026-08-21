# Stage 0-L TAVERN A/B comparison contract

Stage 0-L compares the documented human A/B **analysis files** for Stage 0-K `PAIR_COMPLETE` phrases. It produces integrity/comparison evidence only. It is not a harmony adjudicator and cannot assign a gold tier, a dataset partition, or training authorization.

## Security and input binding

The real-data adapter is bound to:

- TAVERN revision `7cc65dc5365603a92376af50ac71491bea7a16ae`;
- raw archive SHA-256 `b95d85bb3f1e5c0f4ea6df772928d247243485abd93153f0550d6be2fba4fc63`;
- the existing ZIP security inspection gate;
- the Stage 0-K phrase-gate evidence, which must still have gold/split/training authorization set to `false`.

Only phrases for which score + documented Encoder_A + documented Encoder_B are all structurally present are compared. The observed pair count must equal the Stage 0-K A/B queue count. Count mismatch fails closed.

Each analysis member is additionally capped at 2 MiB during the comparator read. Invalid UTF-8, duplicate paths/roles, unsafe ZIP members, annotator directory/filename mismatch, raw-archive hash mismatch, or an unexpected phrase-gate state fail closed.

Encoder_C is not part of this comparison and remains quarantined.

## Comparison classes

The comparator deliberately avoids musical or Roman-numeral semantic normalization.

- `BYTE_EXACT`: A and B are byte-for-byte identical.
- `TEXT_LINE_ENDING_EQUIVALENT`: raw bytes differ, but strict UTF-8 text becomes identical after normalizing only CRLF/CR line endings to LF (and decoding an optional UTF-8 BOM).
- `TEXT_DIFFERENT`: canonical text still differs.

No whitespace trimming, Roman-numeral rewriting, key normalization, spelling correction, or musical inference occurs at this stage.

The output stores only phrase keys, relation labels, and SHA-256 digests of raw/canonical A/B content. It does not copy annotation text into repository evidence.

## Authority boundary

Even `BYTE_EXACT` is **not** automatically `GOLD_CONSENSUS`. Text equality does not by itself prove independent agreement, adjudication, or expert provenance. Stage 0-C gold rules remain authoritative.

Therefore Stage 0-L always emits:

- `adjudication_authorized = false`
- `gold_assignment_authorized = false`
- `partition_assignment_authorized = false`
- `training_authorized = false`

A later human/adjudication policy must decide how equal and differing A/B evidence is used. The 160 B-only phrases, 32 hard-blocked phrases, the 1060-vs-1129 discrepancy, and undocumented Encoder_C are outside Stage 0-L and remain unresolved.
