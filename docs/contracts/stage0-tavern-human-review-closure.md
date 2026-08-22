# Stage 0-O — TAVERN human-review closure contract

## Purpose

Stage 0-O closes the manual TAVERN A/B review workflow without inventing labels that were lost by PDF form persistence. It converts the final two-part human-review result into a bounded, summary-only evidence record and a deterministic resolution plan.

This stage does **not** assign gold tiers, partitions, or training authority.

## Pinned evidence

- Corpus: `TAVERN`
- Revision: `7cc65dc5365603a92376af50ac71491bea7a16ae`
- Stage 0-L A/B comparison SHA-256: `b6f3e80c98acbdeac964ae47f568bf9a6c7eead6efbc221b47d74cdb56293db4`
- Total review pairs: `937`
- Persisted human decisions recovered from the two PDFs: `734`
- Stage 0-M contract-valid human decisions: `694`
- User-reviewed values not persisted by the PDF application: `203`
- Captured choices incompatible with the Stage 0-M relation rule: `40`

The committed evidence is summary-only. It pins the SHA-256 digests of the local PDF/JSON/bundle artifacts but does not commit raw score text, raw A/B annotation text, or the large review files.

## Fail-closed dispositions

Stage 0-O produces exactly three disposition classes:

- `ADMISSIBLE_STAGE0M_HUMAN_INPUT`: only the `694` decisions already valid under Stage 0-M.
- `QUARANTINE_PDF_CAPTURE_LOSS`: `203` records the human reports reviewing but whose selected value was not persisted. No answer is inferred, reconstructed, or substituted.
- `QUARANTINE_SCHEMA_INCOMPATIBLE_CHOICE`: `40` persisted choices that conflict with the Stage 0-M relation/decision contract. They are not silently converted to `CONFIRM_EQUIVALENT` or any gold tier.

## Authority boundary

The following must remain `false` in both the closure summary and resolution plan:

- `gold_assignment_authorized`
- `partition_assignment_authorized`
- `training_authorized`

`eligible_for_gold_mapping_count=694` means only that these records may be considered by a later, separately reviewed gold-mapping contract. It does not make them teacher gold.

## Human-work closure

The user explicitly completed the two-part manual review and asked to finish without another refill cycle. Stage 0-O therefore records:

- `all_records_reviewed_by_human=true`
- `manual_refill_required=false`
- `manual_review_collection_status=CLOSED_WITH_PDF_CAPTURE_LOSS`

This closes manual data entry while preserving capture loss as a technical quarantine condition.

## Security and determinism requirements

Validation fails closed on:

- wrong corpus, revision, or comparison digest;
- count inconsistencies;
- unexpected decision/status keys;
- malformed or missing artifact hashes;
- any authority flag set to true;
- missing human-review attestation;
- silent reopening of manual refill.

Canonical resolution-plan JSON is deterministic and contains no raw annotation text.
