# Stage 2-H — Function event grouped CV

Stage 2-H evaluates the Stage 2-G `ONSET_EVENT` Function targets strictly inside the original TRAIN partition. It joins each private Function onset event to the already-frozen Stage 2-B TRAIN phrase-context feature vector for the same phrase. No event-local duration, segment boundary, harmonic-label rewrite, or inferred timing feature is created.

The development split is inherited unchanged from Stage 1-E. The grouping unit is `split_group_id` (work family), so events and phrases from one work family can never cross fit/evaluation folds. Random event-level or phrase-level splitting is forbidden.

The private Stage 2-G payload remains outside Git. Stage 2-H is pinned to 1,854 materialized Function onset events and private event manifest `d7bbd514ec85b87aee423cae9dce39c74e634ab2f1040fed82af0e25105f255d`. Stage 2-B private records are also required at runtime and remain external.

The grouped-CV runner fits only ephemeral development models inside TRAIN folds. It reports aggregate accuracy, majority-baseline accuracy, fold counts, and the selected frozen smoothing candidate. Scores are model scores, not calibrated probabilities. No final full-TRAIN fit is started, and production authority remains false. VALIDATION, CALIBRATION, and HOLDOUT targets remain inaccessible.
