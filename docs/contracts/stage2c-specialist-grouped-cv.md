# Stage 2-C — specialist TRAIN-only grouped CV

## Purpose

Stage 2-C is the first model-development stage for the specialist decomposition track. It does not reuse the original Stage 0-T VALIDATION partition. Instead it uses only the 487 Stage 0-T TRAIN records materialized by Stage 2-B and the already pinned Stage 1-E three-fold work-family plan.

The first wave remains exactly:

- `ROMAN_NUMERAL_SPECIALIST`
- `KEY_SPECIALIST`
- `FUNCTION_SPECIALIST`

## Exact private input boundary

Stage 2-C accepts only the Stage 2-B private payload whose record-body manifest is:

`cd39690a4be0355a3fbbac303395d4888a89d4204a81af11598e21a822c040cd`

The bounded Stage 2-B receipt records:

- 487 TRAIN records;
- 18 work families;
- fold record counts 156 / 167 / 164;
- 6 / 6 / 6 work families across the three folds;
- 5,265 feature vocabulary entries;
- 94,065 feature occurrences;
- no original VALIDATION, CALIBRATION, or HOLDOUT target access.

The exact `specialist-train.private.json` remains external to Git. The receipt is based on operator-provided summary values and does not claim an exact hash for the summary file itself.

## Model-development policy

Stage 2-C introduces `specialist-multinomial-nb-v1`, a single-target-field Multinomial Naive Bayes development baseline. Each specialist is fitted independently.

The frozen candidate smoothing values are:

`0.25, 0.5, 1.0, 2.0, 4.0`

For each specialist and each candidate alpha:

1. hold out one Stage 1-E development fold;
2. fit only on eligible records from the other two TRAIN folds;
3. evaluate only on eligible records from the held-out TRAIN fold;
4. repeat for all three folds;
5. pool correct/evaluated counts;
6. select the highest pooled acceptable-set accuracy;
7. break an exact tie by choosing the lowest alpha.

The majority-class baseline is computed independently inside each fit-side fold boundary. Preserved A/B variants continue to use equal target weight, and an evaluation prediction is correct when it belongs to the record's canonical unique acceptable target set.

## Safety boundaries

Stage 2-C authorizes only internal development fitting over Stage 0-T TRAIN. It does **not** authorize:

- a final full-TRAIN specialist fit;
- reuse of the original Stage 0-T VALIDATION labels during iteration;
- CALIBRATION access;
- HOLDOUT access;
- event-level target fitting;
- production authority;
- calibrated probability claims.

Model scores remain `MODEL_SCORE_NOT_PROBABILITY`. The deterministic `st-guitar-harmonic-engine` resolver remains authoritative.

## Output boundary

The Stage 2-C runner writes only `stage2c-cv-summary.json` outside the repository. It does not serialize model checkpoints or private target bodies.

The safe summary may contain:

- selected alpha per specialist;
- pooled and per-fold correct/evaluated counts;
- pooled and per-fold accuracies;
- majority-baseline accuracies;
- eligible/missing record counts;
- deterministic-rerun status;
- authority/access flags.

It must not contain private phrase rows, feature vectors, target values, raw annotation text, or model checkpoints.

## Execution

From the exact merged Stage 2-C commit under Python 3.12.8:

```bash
python -m scripts.run_stage2c_specialist_cv \
  /private/STAGE2B_SPECIALIST_TRAIN/specialist-train.private.json \
  /private/STAGE2C_SPECIALIST_CV
```

A successful execution is an internal-CV diagnostic result, not promotion authority. Performance interpretation and any later model-family or representation change require a subsequent stage.
