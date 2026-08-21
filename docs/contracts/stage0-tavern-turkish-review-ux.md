# Stage 0-N2 — Turkish score-aware human review UX

Stage 0-N2 localizes the Stage 0-N1 score-aware TAVERN human-review artifact for the human reviewer. It does not change the Stage 0-M adjudication schema or any machine decision code.

## Visible Turkish decisions

Machine values remain frozen while the reviewer sees these labels:

- `CONFIRM_EQUIVALENT` → **İki analiz eşdeğer**
- `SELECT_A` → **A analizi daha doğru**
- `SELECT_B` → **B analizi daha doğru**
- `PRESERVE_VARIANTS` → **Her iki analiz de müzikal olarak geçerli**
- `AMBIGUOUS` → **Belirsiz — kesin karar veremiyorum**
- `ABSTAIN` → **Atla — bu kayıt için karar vermiyorum**

Relation labels are also localized for display while the underlying evidence relation remains unchanged upstream.

## Safety boundaries

- Raw A/B annotation text inside `<pre>` blocks must remain byte-identical through localization.
- Machine decision values must remain unchanged.
- A preselected radio input is rejected fail-closed.
- Every review card must still contain a Stage 0-N1 score panel.
- Final localized batch and index SHA-256 hashes are recomputed and written to the Stage 0-N2 manifest.
- Gold assignment, partition assignment and training remain unauthorized.
- The localized package is an ephemeral review artifact and must not be committed with raw TAVERN score/annotation content.

## Final manifest

Schema: `st-tavern-score-aware-review-tr-v1`

The final manifest records:

- `review_ui_language = "tr"`
- `score_aware = true`
- `decision_codes_preserved = true`
- `visible_decision_labels_localized = true`
- `decisions_preselected = false`
- final batch SHA-256 values
- final index SHA-256
- all authority flags as `false`

This stage changes presentation only. Human musical adjudication remains the required boundary before any teacher-gold promotion can be considered.
