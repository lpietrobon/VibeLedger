---
id: INV-07
epic: 060-investment-visibility
title: Pin balances and navigation interaction contracts
status: in-progress
dependencies: ["INV-06"]
superseded_by: null
assigned_agent: gpt-5.6-luna
created: 2026-11-10
---

## Acceptance Criteria

- [x] Freeze failing API/UI tests for portfolio totals, account/tax filters, holdings cash handling, observed history, as-of times, missing/stale/unsupported data and drilldown scope.
- [x] Pin the chosen navigation behavior, old Overview routes, empty investment state and continued access to review queues and net worth; preserve exact count-to-drilldown parity.
- [x] Cover mobile/keyboard behavior and visible date/account bounds with synthetic data; record red evidence before implementation.

## Technical Context / Test Plan

Read [the epic](../_epic.md) and [its spirit](../spirit.md). Preserve server-side investment/spending isolation throughout this task. Reuse existing project test directories and synthetic/redacted fixtures; put substantive reports in `artifacts/` prefixed `INV-07` and link them from this log when created. Implementation tasks consume frozen tests; verification tasks require a verifier other than the implementer and actual source-commit evidence.

## Execution Log

- 2026-11-10: Task specified for the staged investment-visibility epic. Not started; no implementation, provider validation, failing-test baseline or independent verification claimed.
- 2026-11-18: GPT-5.6-Luna froze [INV-07 RED evidence](../artifacts/INV-07-red.md) and `tests/test_investment_visibility_tdd.py` at source `648a1e5`. Exact command produced 3 expected failures; no implementation was included.
