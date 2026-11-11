---
id: INV-08
epic: 060-investment-visibility
title: Build the Investments balances and holdings experience
status: todo
dependencies: ["INV-07", "TIME-03"]
superseded_by: null
assigned_agent: null
created: 2026-11-10
---

## Acceptance Criteria

- [ ] Implement the accepted balances/holdings/history UI and server-computed investment summaries, with All investments default and explicit account/tax filters.
- [ ] Reuse the shared date selector/engine; preserve date-epic applicability documentation and do not create conflicting ad hoc window semantics.
- [ ] Implement only the navigation outcome documented in INV-06: replacement is conditional on preserving unique Overview functionality and old-route compatibility. Keep absent performance metrics unavailable rather than zero.
- [ ] Pass frozen UI/API tests and record actual interaction evidence; no production deployment is implied.

## Technical Context / Test Plan

Read [the epic](../_epic.md) and [its spirit](../spirit.md). Preserve server-side investment/spending isolation throughout this task. Reuse existing project test directories and synthetic/redacted fixtures; put substantive reports in `artifacts/` prefixed `INV-08` and link them from this log when created. Implementation tasks consume frozen tests; verification tasks require a verifier other than the implementer and actual source-commit evidence.

## Execution Log

- 2026-11-10: Task specified for the staged investment-visibility epic. Not started; no implementation, provider validation, failing-test baseline or independent verification claimed.
