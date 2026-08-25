# Stage 1-E — private execution handoff

This handoff exists because the full Stage 1-B training payload is intentionally not stored in the public repository.

## Required private input

The materializer requires the exact full Stage 1-B training payload whose manifest digest is:

`79272bbe51d8e850a6b77ca26aa1c7eafb4b728f5b3d25d60a1e62332616e27a`

Do not commit that payload or the complete Stage 1-E record assignment.

## Locked operation

Run in the approved private Python 3.12.8 environment:

`python scripts/materialize_stage1e_internal_cv.py <private-training-payload.json> --summary-only --output <stage1e-summary.json>`

The command fails closed if the source partition distribution, work-family boundary, source digest, or HOLDOUT/CALIBRATION access policy drifts.

## Reviewable output

Only the summary is eligible for later repository review. It must prove:

- 487 eligible TRAIN records;
- 18 TRAIN work families;
- three deterministic folds;
- 6 / 6 / 6 work-family distribution;
- original VALIDATION access false;
- CALIBRATION access false;
- HOLDOUT access false;
- quarantine access false;
- event-target materialization unauthorized;
- training unauthorized by Stage 1-E;
- production authority false;
- canonical record-assignment SHA-256 present.

The full record assignment and private training payload remain external artifacts.
