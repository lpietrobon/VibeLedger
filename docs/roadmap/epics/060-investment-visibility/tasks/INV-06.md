---
id: INV-06
epic: 060-investment-visibility
title: Design Investments visibility and Overview navigation proposal
status: todo
dependencies: ["INV-05", "TIME-01"]
superseded_by: null
assigned_agent: null
created: 2026-11-10
---

## Acceptance Criteria

- [ ] Publish artifacts/INV-06-ux-contract.md with account value/holdings/history layout, account/tax filters, freshness/coverage and not-connected/empty/error states. Reserve later gain/return areas without showing invented numbers.
- [ ] Inventory unique Overview functions and specify destinations for net worth, review queues/count-parity drilldowns and spending summaries. Evaluate Investments in the Overview slot; record the navigation decision and preserve Overview if unique capabilities lack a home.
- [ ] Specify desktop/mobile navigation, default landing route, bookmarked Overview URL behavior, API compatibility, keyboard accessibility and chart/table alternatives.
- [ ] Adopt TIME-01 date bounds and exact-range disclosure; define YTD/1Y/3Y/Since tracked/Custom applicability without equating transaction history with valuation coverage.

## Technical Context / Test Plan

Read [the epic](../_epic.md) and [its spirit](../spirit.md). Preserve server-side investment/spending isolation throughout this task. Reuse existing project test directories and synthetic/redacted fixtures; put substantive reports in `artifacts/` prefixed `INV-06` and link them from this log when created. Implementation tasks consume frozen tests; verification tasks require a verifier other than the implementer and actual source-commit evidence.

## Execution Log

- 2026-11-10: Task specified for the staged investment-visibility epic. Not started; no implementation, provider validation, failing-test baseline or independent verification claimed.
