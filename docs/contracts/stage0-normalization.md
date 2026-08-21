# Stage 0-G — Teacher-gold normalization contract

Normalization is a derived view, never a source rewrite.

Every normalized record keeps three separate authorities:

1. `raw_source_label` — immutable source evidence.
2. `normalized_st_label` — deterministic ST representation.
3. `normalization_version` — exact ruleset identity.

The ST v1 normalized label exposes independent fields for key, local key, Roman numeral, bass, inversion, chord family, extension, suspension, alteration, phrase, and cadence.

The core normalizer deliberately does **not** infer musical meaning. Corpus-specific adapters must provide reviewed deterministic mappings. The core only canonicalizes Unicode/whitespace representation and rejects unknown fields. This prevents an implicit heuristic or future model from silently rewriting teacher-gold.

Changing semantic mapping rules requires a new normalization version; old records remain reproducible.
