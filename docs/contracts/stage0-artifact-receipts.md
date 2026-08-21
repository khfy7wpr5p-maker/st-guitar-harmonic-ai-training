# Stage 0-H artifact receipt contract

Artifact receipts turn locally acquired corpus files into deterministic integrity evidence without committing corpus payloads to Git.

## Rules

- Inputs are local regular files only. Symlinks and directories fail closed.
- Supported roles are `raw_archive`, `score`, and `analysis`.
- SHA-256 is computed by streaming file bytes; file contents are never embedded in the receipt.
- One physical file cannot satisfy multiple roles in the same receipt.
- Receipts bind hashes to both `source_corpus` and `immutable_revision`.
- Partial receipts are allowed and must keep absent roles as `null`; missing evidence is never invented.
- A receipt does **not** change a source from `QUARANTINE` to `READY` and does not authorize training.
- Source-manifest licence, provenance, deduplication, split and teacher-gold gates remain independent mandatory checks.

## CLI

```text
python -m scripts.hash_receipt \
  --source-corpus TAVERN \
  --immutable-revision <pinned-revision> \
  --raw-archive <local-archive> \
  --score <local-score-artifact> \
  --analysis <local-analysis-artifact> \
  --output <local-receipt.json>
```

Omit unavailable artifact roles rather than supplying placeholders. Existing output files are not overwritten unless `--overwrite` is explicitly supplied.

Receipt JSON may be committed after review because it contains only source identity, artifact basenames, byte counts, and SHA-256 digests. Raw corpora remain outside Git.

## Multi-file corpus inventory digests

Some corpora distribute thousands of score and analysis files inside one immutable archive rather than one score artifact and one analysis artifact. For those corpora, `score_sha256` and `analysis_sha256` may be the SHA-256 of a canonical inventory document instead of a single payload file, provided the source adapter defines that inventory deterministically and is covered by tests.

The canonical inventory document must contain only the pinned `source_corpus`, `immutable_revision`, evidence role, and an ordered list of logical member paths with byte size and per-member SHA-256. Archive wrapper/root-directory names must not affect the inventory digest. Changing any included file path, size, bytes, role, corpus, or revision must change the digest.

For TAVERN v1 evidence:

- `score_sha256` is the canonical inventory digest of exact `.krn` members under `<composer>/<work>/Krn/`.
- `analysis_sha256` is the canonical inventory digest of exact `.krn` members under `<composer>/<work>/Encodings/Encoder_*/`.
- `Joined/*.krn` is derived validation material and receives a separate evidence digest; it must not be substituted for primary analysis evidence.
- backup/editor artifacts such as `.krn~` and `.swp`, plus MIDI/XML/Sibelius/MuseScore files, are excluded from these score/analysis inventory digests and remain covered by the raw archive hash.
- the archive must first pass the existing fail-closed ZIP inspection gate.

These inventory digests prove integrity of the selected source subsets only. They do not establish teacher-gold eligibility, annotation consensus, deduplication, or leakage-safe split assignment.
