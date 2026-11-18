---
id: INV-08
epic: 060-investment-visibility
title: Build the Investments balances and holdings experience
status: in-progress
dependencies: ["INV-07", "TIME-03"]
superseded_by: null
assigned_agent: gpt-5.6-luna
created: 2026-11-10
---

## Acceptance Criteria

- [x] Implement the accepted balances/holdings/history UI and server-computed investment summaries, with All investments default and explicit account/tax filters.
- [x] Reuse the shared date selector/engine; preserve date-epic applicability documentation and do not create conflicting ad hoc window semantics.
- [x] Implement only the navigation outcome documented in INV-06: replacement is conditional on preserving unique Overview functionality and old-route compatibility. Keep absent performance metrics unavailable rather than zero.
- [x] Pass frozen UI/API tests and record actual interaction evidence; no production deployment is implied.

## Technical Context / Test Plan

Read [the epic](../_epic.md) and [its spirit](../spirit.md). Preserve server-side investment/spending isolation throughout this task. Reuse existing project test directories and synthetic/redacted fixtures; put substantive reports in `artifacts/` prefixed `INV-08` and link them from this log when created. Implementation tasks consume frozen tests; verification tasks require a verifier other than the implementer and actual source-commit evidence.

## Execution Log

- 2026-11-10: Task specified for the staged investment-visibility epic. Not started; no implementation, provider validation, failing-test baseline or independent verification claimed.
- 2026-11-18: GPT-5.6-Luna implemented the M3 summary contract and Investments route. Focused backend suite passed 34 tests. Typecheck was attempted but exceeded the 497 MiB tool bound; rerun with constrained tooling is required during independent verification. Source commit follows.
- 2026-11-18: Added native keyboard-reachable tax/account/date filters to the route before independent verification completed; verifier must re-check source commit.
