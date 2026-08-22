# Stage 0-N3 — TAVERN Turkish explained-difference review contract

## Purpose

Stage 0-N3 is a human-review usability layer over the frozen Stage 0-N2 Turkish, score-aware TAVERN package. It may make A/B disagreements easier to read, but it MUST NOT decide which analysis is musically correct, create teacher gold, assign a partition, or authorize training.

The two TAVERN annotations are independent expert analyses, not a answer key. The TAVERN README states that analysis and joined files are duplicated for annotators A and B, and that the analyses contain Roman-numeral and phrase-model functional analysis. The original paper likewise describes independent expert analysis and disagreement handling.

## Source-bounded semantic policy

Explanations are deliberately narrower than the raw notation.

Allowed explanatory semantics:

- `T` in the TAVERN function spine: tonic.
- `P` in the TAVERN function spine: pre-dominant.
- `D` in the TAVERN function spine: dominant.
- `.`: Humdrum null token / continuation without a new token in that spine.
- Roman numerals `I` through `VII`: diatonic root scale degree in the prevailing key context.
- `/` inside a harmonic label: secondary / "X of Y" relation to another tonal degree or key area.

The implementation MUST NOT infer undocumented TAVERN function codes. Real pinned data contains values such as `PD` and `A` that are not part of the paper's documented `T/P/D` function set. These values remain raw and are explicitly marked as not automatically interpreted. In particular, `P` and `PD` MUST NOT be silently treated as equivalent.

The implementation also MUST NOT guess the complete meaning of compound source labels such as `2I6/III` merely from visual appearance. It may surface their Roman-root degree and slash relation only where the cited representation contract supports that limited statement.

## Alignment is review assistance, not adjudication

A/B rows are aligned deterministically by bounded structural cues:

1. measure ordinal,
2. parsed reciprocal-duration onset where uniquely available,
3. remaining row order as a fallback.

This alignment is not a musical similarity model and carries no authority. A difference count means only that the raw visible analysis events differ after deterministic alignment; it does not mean that the source contains that many musical errors.

## UI contract

Every review card keeps the pinned score phrase first. Stage 0-N3 then inserts an `A/B fark özeti` with:

- a warning that A and B are not automatic right/wrong answers,
- a small source-supported Turkish glossary,
- tonal-context differences when present,
- a bounded table containing location, A value, B value, and a non-authoritative description of what differs,
- at most 12 visible difference rows by default.

The original raw A/B `<pre>` blocks remain byte-identical and are moved into a collapsible advanced section. They remain available for verification and difficult cases.

## Security and integrity gates

Stage 0-N3 MUST fail closed when:

- the source package is not the expected Stage 0-N2 Turkish schema,
- pair count is not the pinned expected count,
- a source authority flag is already true,
- a decision is preselected,
- a card does not contain exactly two A/B raw blocks,
- required analysis spines cannot be identified,
- a batch filename is outside the bounded `batch-NNN.html` contract,
- an output directory already exists.

Derived explanatory HTML MUST escape untrusted raw tokens. Raw A/B blocks MUST remain unchanged. Final batch and index SHA-256 values MUST be recomputed after enhancement. Partial output MUST be deleted on failure.

## Frozen machine decision contract

Visible Turkish labels may aid the reviewer, but machine values remain unchanged:

- `CONFIRM_EQUIVALENT`
- `SELECT_A`
- `SELECT_B`
- `PRESERVE_VARIANTS`
- `AMBIGUOUS`
- `ABSTAIN`

No option may be preselected.

## Authority

The final manifest MUST preserve:

- `gold_assignment_authorized=false`
- `partition_assignment_authorized=false`
- `training_authorized=false`

Stage 0-N3 is therefore an evidence-display layer only.

## Sources

- Devaney, J., Arthur, C., Condit-Schultz, N., and Nisula, K. (2015), *Theme And Variation Encodings with Roman Numerals (TAVERN): A New Data Set for Symbolic Music Analysis*, ISMIR 2015, pp. 728–734. Public index/PDF: https://ir.webis.de/anthology/2015.ismir_conference-2015.101/
- Pinned TAVERN repository README, revision `7cc65dc5365603a92376af50ac71491bea7a16ae`: https://github.com/jcdevaney/TAVERN/blob/7cc65dc5365603a92376af50ac71491bea7a16ae/README.md
- Humdrum `**harm` representation specification: https://www.humdrum.org/rep/harm/
