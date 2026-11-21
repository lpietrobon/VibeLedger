---
id: INV-13
epic: 060-investment-visibility
title: Pin pooled exposure and editable classification contracts
status: todo
dependencies: ["INV-09"]
superseded_by: null
assigned_agent: null
created: 2026-11-10
---

## Acceptance Criteria

- [ ] Define security exposure separate from instrument type with stocks/bonds/cash/other/unknown, editable sourced/dated fund splits and validation that weights sum to 100 percent.
- [ ] Freeze failing API/UI tests: a 100000 fund at 60/40 contributes 60000 stocks and 40000 bonds; another 20000 cash produces pooled weights 50 percent stocks, one-third bonds and one-sixth cash.
- [ ] Cover unknown assets, stale classifications, target-date fund updates, account selection, missing prices and overrides surviving sync; unknown exposure remains in the denominator and visible, not silently discarded.

## Technical Context / Test Plan

Read [the epic](../_epic.md) and [its spirit](../spirit.md). Preserve server-side investment/spending isolation throughout this task. Reuse existing project test directories and synthetic/redacted fixtures; put substantive reports in `artifacts/` prefixed `INV-13` and link them from this log when created. Implementation tasks consume frozen tests; verification tasks require a verifier other than the implementer and actual source-commit evidence.

## Execution Log

- 2026-11-10: Task specified for the staged investment-visibility epic. Not started; no implementation, provider validation, failing-test baseline or independent verification claimed.
