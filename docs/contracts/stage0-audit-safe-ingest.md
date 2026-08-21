# Stage 0-H — Dataset audit and safe-ingest gate

## Untrusted input boundary

External ZIP, MusicXML/XML, MIDI/binary, TSV/text, JAMS/JSON and related corpus files are untrusted. The Stage 0-H primitives enforce bounded input sizes and fail closed on invalid UTF-8, malformed JSON/XML, duplicate JSON keys/record IDs, XML DTD/entity declarations, ZIP traversal, Windows-style traversal, absolute/drive-like paths, symlinks, duplicate archive paths, excessive member counts/sizes, suspicious compression ratios, and executable/script members.

Extraction is confined to an explicit destination and no archive member is executed.

## Audit output

The deterministic audit reports corpus work counts, gold-tier and split distributions, duplicate clusters, leakage violations, unresolved licenses, missing hashes, missing annotation provenance, corrupt/unsupported samples, class distribution/imbalance warnings, ambiguous gold count, quarantine count, and candidate sources still missing manifests.

Training authorization requires all blockers to be empty, including non-empty TRAIN/VALIDATION/CALIBRATION/HOLDOUT, teacher-gold in CALIBRATION and HOLDOUT, valid normalization versions, no leakage, and at least one READY source.

## Current repository state

`manifests/stage0_audit_input.v1.json` intentionally contains only the approved candidate source names and no fabricated provenance, hashes, licenses or samples. Therefore Stage 0-H must return `HOLD` and `training_authorized=false`.

CI explicitly expects HOLD. Promotion to model training requires a later reviewed PR that supplies real immutable source manifests and leakage-safe sample metadata, obtains a genuine Stage 0-H PASS, and changes the CI expectation from `--expect-hold` to `--expect-pass`.
