# Security policy

## Trust boundary

All external corpora, archives, MusicXML, MIDI, TSV, JAMS, JSON and generated annotations are untrusted input. No external file may be executed. Extraction must occur under an explicitly controlled destination and must reject path traversal, symlink escape, oversized inputs, archive bombs, malformed encodings and schema violations.

## Authority boundary

This repository trains advisory specialist models only. Model output is bounded evidence for `st-guitar-harmonic-engine`; it is never an authoritative harmony result and must not bypass the deterministic resolver. Uncalibrated model scores must not be described as probabilities.

## Repository hygiene

Raw datasets, extracted corpora, checkpoints, model binaries and training runs must not be committed. Only manifests, hashes, immutable revisions, license metadata, split metadata and transformation provenance belong in Git.

## Secrets

Do not commit credentials, tokens, private keys or corpus access secrets. CI runs with least-privilege read permissions and must not expose write credentials to untrusted pull-request code.

## Supply chain

GitHub Actions must be pinned to full commit SHAs. Python runtime is pinned in CI. Stage 0-A intentionally has no third-party Python runtime dependencies.

## Reporting

Security-sensitive failures block merge. Branch protection is preferred but repository process gates remain mandatory even when GitHub branch protection is unavailable or disabled.
