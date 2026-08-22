# Stage 0-V — TAVERN raw-label realization

Stage 0-V closes only the `RAW_LABEL_REALIZATION_PENDING` prerequisite for the 694 human-reviewed TAVERN records. It does not normalize labels, start model training, or alter human decisions.

Pinned inputs:
- TAVERN revision `7cc65dc5365603a92376af50ac71491bea7a16ae`
- archive SHA-256 `b95d85bb3f1e5c0f4ea6df772928d247243485abd93153f0550d6be2fba4fc63`
- validated human decisions SHA-256 `0e53133bf150a101f1b55329c4c5741168fbe7b9ac9a748f221ec07fade1be4a`
- reviewed records: 694

For each `SELECT_A`, `SELECT_B`, or `PRESERVE_VARIANTS` decision, the adapter resolves the exact encoder file from the phrase key and selected source, rereads its bytes from the pinned archive, verifies the human-decision SHA-256 anchor, and verifies strict UTF-8 decodability. Duplicate phrase keys, unsupported decisions, ambiguous member resolution, digest mismatch, malformed ZIPs, unsafe paths, symlinks, excessive archive size/member count, corrupt members, and oversized labels fail closed.

Real result:
- reviewed records: 694
- selected raw labels reread and verified: 747
- source A labels: 55
- source B labels: 692
- verified selected raw bytes: 365851
- realization manifest SHA-256: `39b3cb4f8071605c640621bec20ed9f257f31f638fc6cf717ff9d41ff74bdad3`
- `raw_label_realization_complete=true`

No raw corpus files or label bodies are committed. Evidence stores paths, counts, digests, and an aggregate manifest digest only. `normalization_complete=false` and `training_authorized=false` remain mandatory at this stage.
