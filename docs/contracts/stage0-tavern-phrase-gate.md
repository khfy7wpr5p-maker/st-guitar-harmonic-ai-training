# Stage 0-K TAVERN phrase admission gate

Stage 0-K classifies the already verified Stage 0-I phrase-status totals into review queues. It does **not** inspect or repair raw annotations, assign a gold tier, create dataset partitions, or authorize training.

## Inputs

The gate consumes only committed evidence:

- `stage0i_tavern_structure.v1.json`
- `stage0j_tavern_lineage.v1.json`

Both must remain pinned to TAVERN revision `7cc65dc5365603a92376af50ac71491bea7a16ae`. Any premature training or partition authorization fails closed.

## Deterministic queue policy

| Stage 0-I status | Stage 0-K queue | Decision |
| --- | --- | --- |
| `PAIR_COMPLETE` | `human_pair_adjudication` | Compare human A/B content before any gold decision |
| `SCORE_B_ONLY` | `single_human_review` | Review single-human provenance; no automatic teacher-gold |
| `SCORE_ONLY` | `blocked_missing_annotation` | No human analysis available |
| `ANALYSIS_WITHOUT_SCORE` | `blocked_missing_score` | Score alignment unavailable |
| `DERIVED_OR_UNDOCUMENTED_ONLY` | `quarantine_undocumented_or_derived` | Remain quarantined |

For the committed Stage 0-I evidence this yields:

- 937 `PAIR_COMPLETE` candidates for A/B adjudication,
- 160 `SCORE_B_ONLY` candidates for separate human provenance review,
- 32 hard-blocked phrases (8 score-only, 22 analysis-without-score, 2 derived/undocumented-only),
- 1129 observed phrase keys total.

These counts are queue sizes, **not accepted training samples**.

## Gold safety

`PAIR_COMPLETE` means only that score + documented A + documented B artifacts are structurally present. It does not prove that A and B agree. Therefore Stage 0-K assigns no `GoldTier` at all. A later comparison/adjudication stage must preserve disagreements as variant/ambiguous/abstain evidence according to the Stage 0-C contract.

Likewise, a B-only phrase cannot be promoted to `GOLD_EXPERT` merely because B is a documented human annotator. Expert status and review outcome require explicit provenance evidence.

## Remaining blockers

- the upstream-declared 1060 phrases versus 1129 observed phrase keys remains unresolved;
- A/B content comparison has not run on the real corpus bytes;
- single-human provenance review is incomplete;
- Encoder_C remains undocumented and quarantined.

Therefore all of the following remain false:

- `gold_assignment_authorized`
- `partition_assignment_authorized`
- `training_authorized`
