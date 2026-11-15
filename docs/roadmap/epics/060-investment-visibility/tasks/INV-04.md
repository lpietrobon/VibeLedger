---
id: INV-04
epic: 060-investment-visibility
title: Implement isolated investment ingestion and valuation history
status: done
dependencies: ["INV-03"]
superseded_by: null
assigned_agent: codex
created: 2026-11-10
---

## Acceptance Criteria

- [x] Implement the accepted investment schema/services and dedicated provider synchronization independent of /transactions/sync; reuse encrypted connections and account identities without inserting investment activity into spending transactions.
- [x] Persist securities, holdings, investment activity and as-of valuations with provenance/completeness; support retries, correction reconciliation and independent per-product sync status. Preserve last-good data on partial failure without labeling it fresh.
- [x] Implement canonical domain exclusion and account classification safeguards, including applicable legacy rows; retain inspectable cross-domain evidence and correct consolidated net worth.
- [x] Pass frozen tests; document migration/backup/rollback and deletion/relink behavior. Do not enable production billing or deployment as a side effect of implementation.

## Technical Context / Test Plan

Read [the epic](../_epic.md) and [its spirit](../spirit.md). Preserve server-side investment/spending isolation throughout this task. Reuse existing project test directories and synthetic/redacted fixtures; put substantive reports in `artifacts/` prefixed `INV-04` and link them from this log when created. Implementation tasks consume frozen tests; verification tasks require a verifier other than the implementer and actual source-commit evidence.

## Execution Log

- 2026-11-10: Task specified for the staged investment-visibility epic. Not started; no implementation, provider validation, failing-test baseline or independent verification claimed.

- 2026-11-15: Started only after INV-03 frozen red baseline. Development-only; no production investment call or deployment.
- 2026-11-15: Implemented dedicated models/adapter/atomic ingestion, gated sync and coverage summary, single-count net worth and deletion lifecycle. Frozen tests unchanged. Initial full run 389 passed; supplemental lifecycle/provenance tests added, combined investment suite now 34 passed. Corrected naive/aware freshness timestamp mismatch and missing-account observation timestamp. [Implementation, migration/rollback and limitations](../artifacts/INV-04-implementation.md). Final committed-source regression pending; no deployment or live investment call.
- 2026-11-15: Full run on candidate `f22b4bd`: 391 passed, one compatibility failure because bank-only accounts-summary gained an empty investment coverage field. Fixed by emitting that field only when investment accounts exist; original bank-only response contract retained, not relaxed. Added provider account-type normalization/nickname regression. Final committed correction verification follows.
- 2026-11-15: Corrected candidate `88216f5` full suite passed 393 tests (two existing warnings). Source review identified possible mixing of generic accounts/get balances with earlier investment observation timestamps. Summary now reads the dedicated valuation value/currency paired with that observation; supplemental regression proves a bank balance refresh cannot rewrite it. Focused suite 37 passed; final source verification follows.

- 2026-11-15: Final actual source `f1fee3f`: `python -m pytest -q` — **394 passed**, two pre-existing warnings. Frozen INV-03 test file unchanged from `11c1c61`. Roadmap scan 6 epics/80 tasks/0 issues and diff check clean. Source pushed. Implementation complete; independent INV-05 verdict pending and live INV-01 gate unchanged. Deployed runtime remains `4d2e2f1`; no production schema/config change or investment data call.
