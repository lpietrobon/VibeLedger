---
id: INV-04
epic: 060-investment-visibility
title: Implement isolated investment ingestion and valuation history
status: in-progress
dependencies: ["INV-03"]
superseded_by: null
assigned_agent: codex
created: 2026-11-10
---

## Acceptance Criteria

- [ ] Implement the accepted investment schema/services and dedicated provider synchronization independent of /transactions/sync; reuse encrypted connections and account identities without inserting investment activity into spending transactions.
- [ ] Persist securities, holdings, investment activity and as-of valuations with provenance/completeness; support retries, correction reconciliation and independent per-product sync status. Preserve last-good data on partial failure without labeling it fresh.
- [ ] Implement canonical domain exclusion and account classification safeguards, including applicable legacy rows; retain inspectable cross-domain evidence and correct consolidated net worth.
- [ ] Pass frozen tests; document migration/backup/rollback and deletion/relink behavior. Do not enable production billing or deployment as a side effect of implementation.

## Technical Context / Test Plan

Read [the epic](../_epic.md) and [its spirit](../spirit.md). Preserve server-side investment/spending isolation throughout this task. Reuse existing project test directories and synthetic/redacted fixtures; put substantive reports in `artifacts/` prefixed `INV-04` and link them from this log when created. Implementation tasks consume frozen tests; verification tasks require a verifier other than the implementer and actual source-commit evidence.

## Execution Log

- 2026-11-10: Task specified for the staged investment-visibility epic. Not started; no implementation, provider validation, failing-test baseline or independent verification claimed.

- 2026-11-15: Started only after INV-03 frozen red baseline. Development-only; no production investment call or deployment.
- 2026-11-15: Implemented dedicated models/adapter/atomic ingestion, gated sync and coverage summary, single-count net worth and deletion lifecycle. Frozen tests unchanged. Initial full run 389 passed; supplemental lifecycle/provenance tests added, combined investment suite now 34 passed. Corrected naive/aware freshness timestamp mismatch and missing-account observation timestamp. [Implementation, migration/rollback and limitations](../artifacts/INV-04-implementation.md). Final committed-source regression pending; no deployment or live investment call.
- 2026-11-15: Full run on candidate `f22b4bd`: 391 passed, one compatibility failure because bank-only accounts-summary gained an empty investment coverage field. Fixed by emitting that field only when investment accounts exist; original bank-only response contract retained, not relaxed. Added provider account-type normalization/nickname regression. Final committed correction verification follows.
