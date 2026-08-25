# ST Guitar Harmonic AI Training

Leakage-safe training infrastructure for small harmonic specialist models that provide **bounded advisory evidence** to `st-guitar-harmonic-engine`.

## Non-negotiable authority boundary

Teacher-gold / dataset → specialist AI → validated bounded evidence → deterministic engine resolver → confidence / ambiguity / abstention → authoritative harmonic result.

AI output is never authoritative, never bypasses the deterministic resolver, and uncalibrated model scores are never presented as probabilities.

## Current stage

The repository has progressed through the TAVERN real-data readiness path and the first bounded offline-model infrastructure:

- Stage 0-Q through 0-X: reviewed TAVERN teacher-gold provenance, lineage-safe split, deterministic normalization, and dataset-readiness closure.
- Stage 1-A: bounded training contract and frozen offline-shadow promotion thresholds.
- Stage 1-B1 through 1-B5: hash-bound score inputs, deterministic label-blind features, leakage-safe payload, deterministic model implementation, and final offline-training entry PASS.
- Stage 1-C: sealed offline experiment runner for TRAIN/VALIDATION-only execution. CALIBRATION and HOLDOUT remain excluded from fitting/model selection.
- Stage 1-D: source-derived event-alignment audit. Joined labels remain non-authoritative; 557 reviewed records are event-alignment candidates and 137 remain quarantined for event-level materialization.
- Stage 1-E: deterministic three-fold TRAIN-only work-family plan and fail-closed private record materializer implemented. The 18 TRAIN work families are pinned as 6/6/6 folds; real 487-record materialization remains pending because the full private Stage 1-B payload is intentionally not stored in Git.

The Stage 1-B5 PASS authorizes only the bounded **v1 offline experiment** scope. Stage 1-E does not expand that authority: event-level target materialization, event-level model training, production authority, original VALIDATION access, CALIBRATION access, and HOLDOUT access remain disabled.

The next execution gate is private Stage 1-E record materialization from the hash-pinned Stage 1-B full payload. After that evidence is reviewed, Stage 1-F may separately define event-target materialization.

See [`docs/architecture-status.md`](docs/architecture-status.md) for the current architecture map and [`docs/contracts/stage1e-train-only-development-split.md`](docs/contracts/stage1e-train-only-development-split.md) for the Stage 1-E boundary.

## Repository rule

Do not commit raw corpora, archives, extracted data, private target bodies, full private training payloads, checkpoints, model binaries, or run artifacts. Git stores manifests, immutable source revisions, hashes, license metadata, split metadata, transformation provenance, code, tests, architecture contracts, and bounded audit reports only.
