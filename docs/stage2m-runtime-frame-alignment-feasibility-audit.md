# Stage 2-M — Runtime frame alignment feasibility audit

Stage 2-M is audit-only. It asks one question: can a Stage 2-G Function onset event be matched to the deterministic engine's runtime frame using exact source-grounded identity, without inventing timing or using future/target-derived information?

The current repository reality is **HOLD**. Stage 2-G has 1,854 Function events across 363 materialized source paths, but its private payload does not contain an explicit onset value, duration, segment boundary, or an already established engine runtime-frame identity bridge. Stage 2-L proves that the engine has a causal CURRENT/PREVIOUS feature contract; it does not prove that those runtime frame values can be recovered for Stage 2-G events.

A later alignment bridge may pass only when it provides exact source-path identity, exact event-to-frame identity, and the runtime current-frame pitch-class mask, bass pitch class, and note count. Previous-frame reference is separately reported because it is useful for causal sequence context but is not required merely to establish the current-frame match.

Forbidden: nearest-event matching, index-only matching between independently derived sequences, inferred onset/duration/segment boundaries, NEXT/future context, Teacher-Gold Function as feature, TAVERN harmonic token as runtime feature, Joined harmonic label as authority, AI-generated alignment, and majority/heuristic recovery.

Even a future PASS authorizes only alignment feasibility. It does not authorize feature materialization, model selection, final TRAIN fit, non-TRAIN access, calibrated probability claims, or production authority. The deterministic resolver remains authoritative.
