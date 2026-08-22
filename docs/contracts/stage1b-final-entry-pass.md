# Stage 1-B5 — Final offline-training entry gate

This stage composes the already frozen dataset, threshold, score-input, deterministic-feature, training-payload, model-implementation, and environment-lock evidence. It does not itself fit model parameters.

The gate fails closed if any source identity, count, partition distribution, digest, threshold, model version, seed, dependency lock, variant policy, or authority field drifts.

Required PASS evidence:
- Stage 0-X dataset readiness: PASS
- leakage gate: PASS
- Stage 1-A promotion thresholds: FROZEN and `OFFLINE_SHADOW_ONLY`
- score-input realization: complete for 694 reviewed phrases
- deterministic feature schema: complete
- leakage-safe training payload: complete, 694 records / 747 human-valid targets
- HOLDOUT unavailable to training and model selection
- CALIBRATION unavailable to parameter fitting
- augmentation restricted to TRAIN
- model implementation: `fieldwise-multinomial-nb-v1`
- Python: `3.12.8`
- external dependencies: none
- model seed: `0`
- checkpoint format: canonical JSON only
- pickle loading: forbidden

A PASS authorizes only `OFFLINE_EXPERIMENT_ONLY` training. It does not authorize production, runtime mutation, shadow promotion, calibration, or HOLDOUT access.

After PASS:
- `entry_gate_status=PASS`
- `training_authorized=true`
- `training_scope=OFFLINE_EXPERIMENT_ONLY`
- `model_training_started=false`
- `production_authority=false`
- `holdout_access_during_training=false`
- `holdout_access_during_model_selection=false`

The first model run must fit on TRAIN only and evaluate on VALIDATION only. Promotion thresholds are already frozen and must not be changed in response to the first run. CALIBRATION and HOLDOUT remain sealed until their separately authorized stages.
