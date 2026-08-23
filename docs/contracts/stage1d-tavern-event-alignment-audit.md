# Stage 1-D — TAVERN source-derived event-alignment audit

Stage 1-D investigates whether TAVERN `Joined` files can safely support a future event-level harmony representation after the Stage 1-C whole-phrase model path was prepared. This stage does **not** train a model and does not materialize new event-level teacher gold.

## Authority boundary

The existing 694 HUMAN-reviewed decisions remain the only authority for choosing annotator A, annotator B, or preserving both variants. `Joined` files are treated only as `SOURCE_DERIVED_ALIGNMENT_CARRIER_ONLY` evidence.

The harmonic labels embedded in `Joined` are **never** promoted to teacher gold, never used to override the selected Encoder A/B raw analysis, and never used as model targets in this stage. This is necessary because TAVERN documents Joined as analysis+score files per annotator, but the corpus does not provide a versioned transformation contract proving that Joined harmonic syntax is byte- or token-equivalent to the Encoder source syntax.

## Deterministic alignment criterion

For each selected HUMAN target path:
1. reread the exact Encoder A/B file from the pinned TAVERN archive;
2. require its SHA-256 to equal the human-adjudication anchor;
3. resolve exactly one same-phrase, same-annotator Joined file under the documented filename convention;
4. require strict UTF-8 and exactly one harmonic analysis spine;
5. require the Joined carrier to contain a `**kern` spine;
6. extract only the leading reciprocal-duration sequence from harmonic data events using the same conservative prefix grammar already used by the Stage 0-W normalization adapter;
7. admit an alignment **candidate** only when the Encoder and Joined reciprocal-duration sequences are textually identical and every selected Encoder harmonic event has an explicit reciprocal duration.

No inversion, Roman-numeral, function, enharmonic, cadence, or musical-equivalence mapping is inferred.

For `PRESERVE_VARIANTS`, both A and B selected paths must independently satisfy the criterion. If either path fails, the entire variant record remains QUARANTINE for event-level materialization; one surviving variant may not silently replace the pair.

## Real pinned audit

Pinned source:
- TAVERN revision: `7cc65dc5365603a92376af50ac71491bea7a16ae`
- archive SHA-256: `b95d85bb3f1e5c0f4ea6df772928d247243485abd93153f0550d6be2fba4fc63`
- validated HUMAN decisions SHA-256: `0e53133bf150a101f1b55329c4c5741168fbe7b9ac9a748f221ec07fade1be4a`

Observed over 694 reviewed records / 747 selected A/B target paths:
- reciprocal-duration sequence exact: **600** paths
- reciprocal-duration sequence mismatch or incomplete: **147** paths
- Joined harmonic label sequence exactly matches selected Encoder syntax: **47** paths
- Joined harmonic label sequence is not exact: **700** paths
- record-level event-alignment candidates: **557**
  - expert candidates: **519**
  - variant candidates with both selected paths aligned: **38**
- record-level QUARANTINE: **137**
- harmonic event paths represented by alignment candidates: **6534**
- full private audit manifest SHA-256: `95fdae9b9d336eb9c50646b2c980954d54c87dac95902974b1836dad77ff7552`

The 47/700 label result is evidence that Joined labels must not be substituted for the human-selected raw Encoder labels. Stage 1-D intentionally uses only source identity plus reciprocal event structure for candidate alignment.

## Leakage and model-development consequence

Stage 1-D does not evaluate model quality and does not read CALIBRATION or HOLDOUT for fitting, threshold tuning, or model selection. No validation threshold is changed.

Because Stage 1-C has already exposed one diagnostic validation result outside the locked official runtime, future representation/model iteration must not repeatedly optimize against the frozen VALIDATION partition. Before any event-level model v2 development, a separate TRAIN-only internal development split/CV contract must be created from the existing TRAIN work families. Original VALIDATION, CALIBRATION, and HOLDOUT remain outside that iterative development loop.

## Current gate

- `joined_labels_authoritative=false`
- `joined_labels_used_as_targets=false`
- `event_target_materialization_authorized=false`
- `model_training_started=false`
- `training_authorized=false`
- `production_authority=false`

The next safe step is a TRAIN-only internal development split followed by a separately reviewed event-target materialization contract. The 137 quarantined records require no new human decision; they simply remain outside event-level v2 until a stronger deterministic alignment proof exists.
