# Stage 0-N1 TAVERN score-aware human review contract

Stage 0-N1 corrects the human-review evidence gap discovered in Stage 0-N: Annotator A and B cannot be adjudicated musically from annotation text alone. Every review record must show the corresponding pinned TAVERN phrase score before a human decision is made.

## Supersession

The original Stage 0-N package is **not sufficient for teacher-gold adjudication** because it lacks a musical score reference. It remains useful only as a non-authoritative A/B text inspection artifact. Human adjudication must use the Stage 0-N1 score-aware package or a later contract that preserves the same evidence boundary.

## Immutable source binding

The score-aware package is bound to:

- TAVERN revision `7cc65dc5365603a92376af50ac71491bea7a16ae`;
- raw archive SHA-256 `b95d85bb3f1e5c0f4ea6df772928d247243485abd93153f0550d6be2fba4fc63`;
- the Stage 0-L comparison evidence and Stage 0-M adjudication boundary already enforced by Stage 0-N;
- exactly `937` A/B review records.

A missing score, duplicate phrase score, archive hash mismatch, unsafe ZIP member, invalid UTF-8 score, unexpected spine mismatch, or phrase-count mismatch fails closed and removes a partial output directory.

## Score evidence shown to the reviewer

For each A/B pair the package reads the phrase-level `Krn/*_score.krn` member from the pinned TAVERN archive and renders an offline inline SVG reference above Annotator A and Annotator B.

The renderer preserves review-relevant symbolic evidence from `**kern`:

- staff assignment;
- pitch height and accidentals;
- measure boundaries;
- basic written durations, noteheads and stems;
- simultaneous/aligned onset rows;
- source phrase identity and score SHA-256.

Horizontal spacing is normalized for review readability. Beam and slur engraving is simplified. Therefore this is a **review reference**, not a publication-quality engraving or a new symbolic analysis. If the visual evidence is unclear, the reviewer must use `AMBIGUOUS` or `ABSTAIN` rather than infer missing information.

## Pinned source anomalies

Two phrase files in the pinned TAVERN archive expose three data columns after a two-spine header before a later explicit merge:

- `Beethoven/B064:03:02`
- `Beethoven/B064:03:03`

Stage 0-N1 permits one narrowly scoped compatibility interpretation for exactly these two phrase keys: an implicit split of the rightmost staff-1 spine. The package visibly records a source warning for these phrases. No generic repair rule is allowed for other phrase keys; any other unexpected spine mismatch fails closed.

## Human-only decision boundary

The score renderer never selects or recommends Annotator A or B. Radio inputs remain unselected. The existing Stage 0-M decision vocabulary and relation constraints remain authoritative:

- `CONFIRM_EQUIVALENT`
- `SELECT_A`
- `SELECT_B`
- `PRESERVE_VARIANTS`
- `AMBIGUOUS`
- `ABSTAIN`

The exported decision JSON remains evidence-bound to the A/B hashes and is still subject to Stage 0-M validation.

## Security and repository policy

Raw score and annotation material exists only in the generated short-lived review artifact. It is not committed to Git. Source text is not interpreted as executable HTML or JavaScript. Score comments are ignored by the renderer, annotation text remains escaped, and the package keeps the restrictive offline CSP inherited from Stage 0-N.

Stage 0-N1 always keeps:

- `gold_assignment_authorized = false`
- `partition_assignment_authorized = false`
- `training_authorized = false`

Human decisions must still pass Stage 0-M and a later explicit teacher-gold mapping contract before any dataset admission or training authorization can change.
