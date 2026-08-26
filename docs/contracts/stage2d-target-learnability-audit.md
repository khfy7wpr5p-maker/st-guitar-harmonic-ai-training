# Stage 2-D — TRAIN-only target learnability audit

## Purpose

Stage 2-C showed a strong Key specialist learning signal but no improvement for Function and zero grouped-CV accuracy for Roman Numeral. Stage 2-D does **not** change the model family, smoothing candidates, split, or thresholds. It measures whether the current specialist targets are learnable as closed-set phrase-level classes under the existing 3-fold work-family boundary.

The audit is diagnostic only.

## Input boundary

Stage 2-D accepts only the exact external Stage 2-B private payload already pinned by Stage 2-C:

- schema: `st-stage2b-specialist-train-materialization-v1`
- private record manifest SHA-256: `cd39690a4be0355a3fbbac303395d4888a89d4204a81af11598e21a822c040cd`
- records: 487
- work families: 18
- development folds: 3
- group-plan SHA-256: `ae15ed507247548907815f8ee1a5586f9fa2384a32d5102e887ddedff52e1a4c`

The existing Stage 2-C private-payload validator is reused fail-closed before any learnability statistics are computed.

## Audit questions

For each of `ROMAN_NUMERAL_SPECIALIST`, `KEY_SPECIALIST`, and `FUNCTION_SPECIALIST`, Stage 2-D reports only aggregate statistics:

1. eligible and missing record counts;
2. target occurrence count;
3. unique target count;
4. unique-target-per-record ratio;
5. target reuse factor;
6. singleton target count/fraction;
7. multi-target record count;
8. how many unique targets occur in exactly 1, 2, or all 3 development folds;
9. per-fold fit/evaluation unique-target overlap;
10. per-fold unseen target occurrence rate;
11. records whose held-out acceptable set contains no target seen in the fit folds;
12. a closed-set oracle ceiling: the maximum possible record-level acceptable-set accuracy for a classifier restricted to classes observed in the fit folds;
13. privacy-safe sequence-length summaries for Roman Numeral and Function targets.

No target string/token is serialized into the summary.

## Sequence target semantics

The current TAVERN normalization adapter stores:

- Roman Numeral as canonical JSON array text, e.g. a phrase-level harmonic token sequence;
- Function as canonical JSON array text, e.g. a phrase-level function sequence;
- Key as a scalar target.

Stage 2-D parses the JSON arrays only to count their lengths. It does not expose sequence elements.

## Closed-set oracle ceiling

For a held-out record, if **none** of its acceptable targets appears anywhere in the two fit folds, a conventional closed-set classifier trained only on those folds cannot produce a correct acceptable-set class without inventing an unseen class.

For each fold:

`closed_set_oracle_ceiling = 1 - records_with_no_seen_acceptable_target / evaluation_record_count`

This is not a model score and not a probability. It is a structural upper bound for the current phrase-level closed-set target formulation.

## Security and authority invariants

Stage 2-D must keep all of the following true:

- audit scope: `STAGE0_T_TRAIN_TARGETS_ONLY`
- original VALIDATION target access: false
- CALIBRATION target access: false
- HOLDOUT target access: false
- model fitting: false
- model selection: false
- full-TRAIN final fitting: false
- checkpoint output: none
- event-level training authority: false
- production authority: false
- deterministic resolver remains authoritative: true

The audit cannot authorize promotion or change any Stage 2-C result.

## Output

The external runner writes only:

`stage2d-learnability-summary.json`

The output contains counts, ratios, fold overlap statistics, and sequence-length statistics. It contains no private records, target values, feature vectors, raw TAVERN text, or model checkpoint.

## Decision use

Stage 2-D is intended to distinguish among three different failure modes:

- **target-space sparsity / unseen-class failure** — redesign the target representation before trying a larger model;
- **adequate class reuse but weak feature/model discrimination** — improve label-blind features and/or the specialist model;
- **healthy internal learnability** — preserve the target formulation and continue controlled specialist development.

Original VALIDATION remains untouched during this decision.
