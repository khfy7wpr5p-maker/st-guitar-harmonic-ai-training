# ST Guitar Harmonic AI Training

Leakage-safe training infrastructure for small harmonic specialist models that provide **bounded advisory evidence** to `st-guitar-harmonic-engine`.

## Non-negotiable authority boundary

Teacher-gold / dataset → specialist AI → validated bounded evidence → deterministic engine resolver → confidence / ambiguity / abstention → authoritative harmonic result.

AI output is never authoritative, never bypasses the deterministic resolver, and uncalibrated model scores are never presented as probabilities.

## Current stage

Stage 0-A through Stage 0-H infrastructure is implemented. The real-data Stage 0-H gate remains **HOLD** because no external corpus has yet been admitted with verified immutable provenance/hashes/licenses and no leakage-safe teacher-gold sample manifest exists yet.

**Real model training is not authorized.** CI asserts this fail-closed state and will fail if training becomes authorized without an explicit promotion change.

## Repository rule

Do not commit raw corpora, archives, extracted data, checkpoints, model binaries, or run artifacts. Git stores manifests, immutable source revisions, hashes, license metadata, split metadata, transformation provenance, code, tests, and audit reports only.
