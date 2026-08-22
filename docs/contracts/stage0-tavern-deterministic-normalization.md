# Stage 0-W — TAVERN deterministic normalization

Stage 0-W closes only the `DETERMINISTIC_NORMALIZATION_PENDING` prerequisite for the 694 reviewed TAVERN records. It consumes Stage 0-V hash-verified selected labels and maps them to `st-harmony-normalization-v1` without musical inference. It does not start or authorize model training.

## Authority and source preservation

The pinned raw TAVERN annotation remains the source authority. The adapter rereads every selected archive member, verifies its Stage 0-V raw SHA-256 again, decodes strict UTF-8, and builds a `NormalizationRecord` whose `raw_source_label` is the untouched decoded source text. Serialized target evidence omits the raw body and stores only its SHA-256 plus the normalized representation.

## Conservative mapping

TAVERN review records are phrase-level objects, while the ST v1 normalized fields are scalar strings. Therefore source event sequences are represented deterministically as compact JSON arrays inside the relevant scalar field rather than being musically collapsed:

- first explicit key interpretation → `key`
- later explicit key interpretations, in source order → `local_key` as a compact JSON sequence
- `**harm` or `**chords` data tokens, in source order → `roman_numeral` as a compact JSON sequence
- `**function` data tokens, when the spine exists → `phrase` as a compact JSON sequence
- `bass`, `inversion`, `chord_family`, `extension`, `suspension`, `alteration`, and `cadence` remain null in adapter v1

Only the explicit leading Humdrum reciprocal-duration prefix is removed from harmonic/function data tokens. The remaining token is preserved literally. In particular undocumented function codes such as `PD` and `A` are not interpreted, merged, renamed, or treated as equivalent to documented `P/T/D` values.

No implicit modulation, inversion, chord family, cadence, or missing semantic value is inferred. A future semantic expansion requires a reviewed new adapter/version rather than silently changing v1 output.

## Structural irregularities

The adapter requires exactly one exclusive-interpretation header and exactly one harmonic analysis spine (`**harm` or `**chords`). `**function` is optional and at most one such spine is accepted. Source rows with a width different from the declared header are not repaired: only an actually present cell at the declared analysis-spine index is read, and the irregularity is counted in evidence.

Real selected-target structure:
- 747 normalized targets across 694 reviewed records
- `**chords`: 644
- `**harm`: 103
- function spine present: 739
- function spine absent: 8
- explicit key present: 692
- multiple explicit key interpretations: 1
- source files with row-width irregularities: 53
- irregular rows: 246
- harmonic source tokens preserved: 8340
- function source tokens preserved: 3288

Normalized-target manifest SHA-256: `195ec1ce2193f8560043a94f3ea99c8db69b830fff6e60313c88565714450a4c`.

## Safety gates

The stage fails closed on archive or selected-label digest mismatch, malformed/corrupt/unsafe ZIP input, duplicate phrase keys or selected sources, source/decision mismatch, malformed analysis spines, absent harmonic data, unexpected upstream training authority, count drift, or source identity drift.

Final authority remains:
- `raw_label_realization_complete=true`
- `normalization_complete=true`
- `training_authorized=false`

Stage 0-W therefore prepares deterministic teacher-gold targets but cannot itself open the model-training gate.
