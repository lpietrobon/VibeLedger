---
id: INV-16
epic: 060-investment-visibility
title: Freeze return methodology and numerical oracles
status: todo
dependencies: ["INV-12"]
superseded_by: null
assigned_agent: null
created: 2026-11-10
---

## Acceptance Criteria

- [ ] Publish artifacts/INV-16-return-contract.md covering one engine parameterized by selected accounts and exact window, money-weighted XIRR and time-weighted methods, flow timing, opening/closing valuation rules and supported-history thresholds.
- [ ] Define personal-return default, period versus annualized conversion, no annualization for short periods by default, and handling of no/multiple roots, zero/negative capital, irregular flows and missing valuations. Exact TWR needs supported flow-boundary valuations; any approximation must be explicitly named and qualified.
- [ ] Freeze independently derived numerical fixtures and tolerances before implementation, covering no-flow and timed-flow portfolios, same-day/in-kind transfers, corrections, account subsets and pooled calculation. Do not average account return percentages.
- [ ] Add failing backend/UI tests for YTD/1Y/3Y/Since tracked/Custom, insufficient history, stale data, cash-flow signs, leap-year/day-count conventions, undefined results, annualization labels and inspectable methodology.

## Technical Context / Test Plan

Read [the epic](../_epic.md) and [its spirit](../spirit.md). Preserve server-side investment/spending isolation throughout this task. Reuse existing project test directories and synthetic/redacted fixtures; put substantive reports in `artifacts/` prefixed `INV-16` and link them from this log when created. Implementation tasks consume frozen tests; verification tasks require a verifier other than the implementer and actual source-commit evidence.

## Execution Log

- 2026-11-10: Task specified for the staged investment-visibility epic. Not started; no implementation, provider validation, failing-test baseline or independent verification claimed.
