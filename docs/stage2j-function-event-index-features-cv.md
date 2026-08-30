# Stage 2-J — Function event index features + grouped CV

Stage 2-J is a TRAIN-only development experiment after the Stage 2-I audit. It keeps the frozen Stage 2-B phrase-context features and adds exactly two existing Stage 2-G event-order fields as categorical one-hot features: `FUNCTION_EVENT_INDEX` and `CARRIER_HARMONIC_EVENT_INDEX`.

No arithmetic gap feature is created. `carrier_source_order_index`, A/B source provenance, explicit onset, duration, segment boundaries, local harmonic labels, and local score context are not model features. Function targets are preserved exactly and are never rewritten.

The runner uses the unchanged Stage 1-E work-family folds and evaluates both the phrase-only reference representation and the index-augmented representation on the same TRAIN-only grouped-CV split. This makes the index contribution measurable without opening VALIDATION, CALIBRATION, or HOLDOUT.

All fitted models are ephemeral CV models. Stage 2-J does not start a full-TRAIN final fit, does not emit calibrated probabilities, and does not grant production authority. The deterministic harmonic resolver remains authoritative.
