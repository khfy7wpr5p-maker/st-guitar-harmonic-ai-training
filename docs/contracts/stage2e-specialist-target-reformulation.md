# Stage 2-E — Specialist target reformulation

## Status

Implementation gate only. No model fitting, model selection, final full-TRAIN fit, event-target materialization, event-level training, calibration, HOLDOUT access, original VALIDATION access, or production authority is granted by this stage.

## Evidence basis

Stage 2-E responds to the TRAIN-only Stage 2-D learnability diagnostic over the exact Stage 2-B private specialist payload:

- Stage 2-B private record manifest SHA-256: `cd39690a4be0355a3fbbac303395d4888a89d4204a81af11598e21a822c040cd`;
- Stage 1-E grouped-CV plan SHA-256: `ae15ed507247548907815f8ee1a5586f9fa2384a32d5102e887ddedff52e1a4c`;
- Stage 1-D event-alignment manifest SHA-256: `95fdae9b9d336eb9c50646b2c980954d54c87dac95902974b1836dad77ff7552`.

The Stage 2-D private summary was provided operationally. `evidence/stage2d_private_learnability_receipt.v1.json` records only bounded aggregate values and explicitly does **not** claim that the exact private summary file SHA-256 is repository-bound.

Observed TRAIN-only target-space results:

| Specialist | Unique targets | Singleton fraction | Pooled unseen rate | Closed-set oracle ceiling |
| --- | ---: | ---: | ---: | ---: |
| Key | 12 | 0.083333 | 0.015184 | 0.984816 |
| Function | 101 | 0.564356 | 0.271784 | 0.734310 |
| Roman Numeral | 432 | 0.909722 | 1.000000 | 0.000000 |

## Architectural decision

### Key specialist

The current `key` target is a scalar class and remains structurally learnable under the grouped TRAIN folds. Stage 2-E therefore preserves the scalar target formulation.

This does **not** authorize another model run. A separate TRAIN-only model/feature gate is required before further fitting.

### Function specialist

The current `phrase` target is a whole-phrase JSON sequence serialized as one closed-set class. Stage 2-D shows substantial target sparsity and non-trivial unseen held-out classes.

Stage 2-E retires this whole-phrase classification target. The intended replacement is an aligned function event/token sequence, but no authoritative Function event carrier alignment has yet been proven.

Required next prerequisite:

`FUNCTION_EVENT_CARRIER_ALIGNMENT_AUDIT_REQUIRED`

No Function event target may be materialized or trained before that audit establishes a label-to-score/event boundary using only admitted TRAIN data.

### Roman Numeral specialist

The current `roman_numeral` target is also a whole-phrase JSON sequence serialized as one class. Stage 2-D proves that this formulation is unusable for grouped closed-set classification:

- pooled unseen target occurrence rate = `1.0`;
- pooled closed-set oracle ceiling = `0.0`;
- 432 unique targets from 496 target occurrences;
- 90.97% of unique targets are singletons.

Stage 2-E therefore retires whole-phrase Roman-numeral classification. The intended replacement is an aligned harmonic event sequence.

Stage 1-D already provides event-alignment **candidates**, not authoritative event targets. Stage 1-E still keeps event-target materialization disabled. Therefore Roman event-target work requires both:

1. a private TRAIN-only Stage 1-E event materialization handoff; and
2. a later Stage 1-F contract explicitly authorizing the event-target boundary.

Stage 1-D quarantined records remain excluded and may not be silently reused.

## Fail-closed authority

The machine-readable Stage 2-E contract keeps all of the following false:

- `model_fitting_authorized`;
- `model_selection_authorized`;
- `full_train_final_fit_authorized`;
- `event_target_materialization_authorized`;
- `event_level_training_authorized`;
- `original_validation_target_access`;
- `calibration_target_access`;
- `holdout_target_access`;
- `production_authority`;
- `calibrated_probability_output`.

The deterministic `st-guitar-harmonic-engine` resolver remains authoritative.

## Next safe work

Stage 2-E deliberately splits the track:

- **Key:** design a separate TRAIN-only feature/model improvement gate using the existing scalar target;
- **Function:** perform a TRAIN-only function event-carrier alignment audit before any target materialization;
- **Roman Numeral:** complete the private TRAIN-only Stage 1-E event materialization prerequisite, then define Stage 1-F before event-target training.

No original VALIDATION, CALIBRATION, or HOLDOUT target may be opened while these development choices are made.
