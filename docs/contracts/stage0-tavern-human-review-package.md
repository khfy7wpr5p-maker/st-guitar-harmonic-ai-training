# Stage 0-N TAVERN human review package contract

Stage 0-N prepares the 937 Stage 0-L A/B comparison pairs for **human musical review**. It is a presentation/export layer only. It does not adjudicate music, assign teacher-gold tiers, create data partitions, or authorize training.

## Immutable inputs

The production review package is bound to:

- TAVERN revision `7cc65dc5365603a92376af50ac71491bea7a16ae`;
- raw archive SHA-256 `b95d85bb3f1e5c0f4ea6df772928d247243485abd93153f0550d6be2fba4fc63`;
- Stage 0-L full comparison evidence SHA-256 `b6f3e80c98acbdeac964ae47f568bf9a6c7eead6efbc221b47d74cdb56293db4`;
- exactly 937 A/B pairs.

The Stage 0-M validator is reused with an empty decision set before package generation. Wrong source revision, authority state, pair count, phrase key, comparison digest, relation counts, or A/B raw-content hashes fail closed.

## Raw-data boundary

The review pages necessarily display the human A/B annotation text so a human can make a musical decision. These raw annotation texts are **never committed to Git**.

Generated review files must live either outside the repository or under the already-gitignored `/artifacts` directory. The GitHub Actions workflow writes them only to `/tmp` and uploads them as a short-lived Actions artifact.

The package records:

- `raw_annotation_text_in_ephemeral_package = true`;
- `raw_annotation_text_committed = false`.

TAVERN content is attributed as CC BY-SA 4.0 and linked back to the upstream repository.

## Browser safety

TAVERN annotation text is treated as untrusted input. It is HTML-escaped before display. Review pages use a restrictive Content Security Policy that blocks network connections, remote media, frames, objects, and form submission. No source text is inserted into executable JavaScript.

No decision is preselected.

## Human decisions

Allowed options follow Stage 0-M exactly:

- `BYTE_EXACT` or `TEXT_LINE_ENDING_EQUIVALENT`: `CONFIRM_EQUIVALENT`, `PRESERVE_VARIANTS`, `AMBIGUOUS`, `ABSTAIN`;
- `TEXT_DIFFERENT`: `SELECT_A`, `SELECT_B`, `PRESERVE_VARIANTS`, `AMBIGUOUS`, `ABSTAIN`.

A review page exports only the choices the human explicitly selected. Unselected records remain pending.

Exported JSON uses the Stage 0-M `st-tavern-human-adjudication-v1` schema and includes phrase key plus the exact A/B raw SHA-256 anchors. The reviewer reference should be opaque and should not contain unnecessary personal information.

## Batching

The default batch size is 25, giving 38 review pages for 937 pairs. Batch size is bounded from 1 through 50. Each generated page has its own SHA-256 recorded in `manifest.json`. The package also contains `index.html` and a hash-bound manifest.

## Authority invariants

Every package manifest must retain:

- `decisions_preselected = false`;
- `gold_assignment_authorized = false`;
- `partition_assignment_authorized = false`;
- `training_authorized = false`.

A complete human review is still only adjudication evidence. Teacher-gold mapping remains a later explicit Stage 0-C-governed step.

The 160 B-only records, 32 hard-blocked records, the 1060-vs-1129 discrepancy, undocumented Encoder_C, and unresolved external-corpus admission remain outside Stage 0-N.
