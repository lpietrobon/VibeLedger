---
id: INV-07
epic: 060-investment-visibility
title: Pin balances and navigation interaction contracts
status: todo
dependencies: ["INV-06"]
superseded_by: null
assigned_agent: null
created: 2026-11-10
---

## Acceptance Criteria

- [ ] Freeze failing API/UI tests for portfolio totals, account/tax filters, holdings cash handling, observed history, as-of times, missing/stale/unsupported data and drilldown scope.
- [ ] Pin the chosen navigation behavior, old Overview routes, empty investment state and continued access to review queues and net worth; preserve exact count-to-drilldown parity.
- [ ] Cover mobile/keyboard behavior and visible date/account bounds with synthetic data; record red evidence before implementation.

## Technical Context / Test Plan

Read [the epic](../_epic.md) and [its spirit](../spirit.md). Preserve server-side investment/spending isolation throughout this task. Reuse existing project test directories and synthetic/redacted fixtures; put substantive reports in `artifacts/` prefixed `INV-07` and link them from this log when created. Implementation tasks consume frozen tests; verification tasks require a verifier other than the implementer and actual source-commit evidence.

## Execution Log

- 2026-11-10: Task specified for the staged investment-visibility epic. Not started; no implementation, provider validation, failing-test baseline or independent verification claimed.
