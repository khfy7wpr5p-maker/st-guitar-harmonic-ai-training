# Stage 0-M TAVERN human adjudication contract

Stage 0-M validates **human review decisions** for the 937 documented TAVERN A/B pairs produced by Stage 0-L. It is deliberately downstream of the real comparison evidence and upstream of any teacher-gold assignment.

## Immutable evidence binding

The default gate is pinned to:

- TAVERN revision `7cc65dc5365603a92376af50ac71491bea7a16ae`;
- Stage 0-L full comparison evidence SHA-256 `b6f3e80c98acbdeac964ae47f568bf9a6c7eead6efbc221b47d74cdb56293db4`;
- exactly `937` A/B comparison records.

A different comparison file, pair count, source revision, authority state, relation-count summary, phrase key, or A/B raw-content hash fails closed.

## Human authority boundary

`reviewer_type` must be exactly `HUMAN`. Automated/model reviewers are rejected. `reviewer_ref` should be an opaque reviewer identifier; do not place unnecessary personal information in the record.

Each decision must be anchored to the exact phrase key and the Stage 0-L A/B raw SHA-256 values. Duplicate or unknown phrase decisions are rejected.

Allowed decisions are:

- `CONFIRM_EQUIVALENT` — permitted only for `BYTE_EXACT` or `TEXT_LINE_ENDING_EQUIVALENT` evidence;
- `SELECT_A` — permitted only for `TEXT_DIFFERENT` evidence;
- `SELECT_B` — permitted only for `TEXT_DIFFERENT` evidence;
- `PRESERVE_VARIANTS` — preserve both human variants without choosing one;
- `AMBIGUOUS` — retain unresolved musical ambiguity;
- `ABSTAIN` — reviewer explicitly declines to decide.

The gate never infers a decision from the comparison relation. In particular, `BYTE_EXACT` is not automatically consensus, and `TEXT_DIFFERENT` is never silently resolved in favor of A or B.

## Output and privacy

The generated gate contains phrase keys, decisions, comparison relations, A/B raw-content hashes, reviewer/session references, and aggregate counts. It does not copy raw annotation text.

A partial review is valid evidence but remains `review_status = INCOMPLETE`. A complete 937-pair review becomes `review_status = COMPLETE`, but completion still does **not** authorize teacher-gold assignment.

Stage 0-M always emits:

- `gold_assignment_authorized = false`
- `partition_assignment_authorized = false`
- `training_authorized = false`

Teacher-gold mapping remains a later explicit contract governed by Stage 0-C provenance rules. Cross-corpus dedup, split assignment, the 160 B-only records, 32 hard-blocked records, the 1060-vs-1129 discrepancy, and undocumented Encoder_C remain outside this stage.
