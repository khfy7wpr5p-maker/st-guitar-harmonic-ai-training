# Stage 2-I — Function event feature alignment audit

Stage 2-I is an audit-only stage after the Stage 2-H grouped-CV HOLD. It does not fit a model and does not authorize feature materialization.

The audit reads only the frozen private Stage 2-G TRAIN Function onset-event payload. It verifies the already-materialized event/order fields `function_event_index`, `carrier_harmonic_event_index`, and `carrier_source_order_index`, plus A/B provenance. It reports aggregate coverage, path-level ordering integrity, event-count statistics, carrier gaps, and bounded Function target-cardinality statistics without serializing private targets or per-event identities.

Two fields are considered structurally suitable candidates for a later feature-materialization contract: `FUNCTION_EVENT_INDEX` and `CARRIER_HARMONIC_EVENT_INDEX`. `CARRIER_SOURCE_ORDER_INDEX` is format-sensitive and remains audit-only. Source A/B provenance is not authorized as a model feature.

Stage 2-G does not serialize an explicit onset value, duration, segment boundary, local harmonic-label context, or local score context. Stage 2-I therefore does not invent or infer any of them. VALIDATION, CALIBRATION, and HOLDOUT remain closed, and production authority remains false.
