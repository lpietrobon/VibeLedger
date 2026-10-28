---
id: TIME-01
epic: 050-shared-date-range-semantics
title: Inventory date-filtered surfaces and settle an explicit date/comparison contract
status: todo
dependencies: []
superseded_by: null
assigned_agent: null
created: 2026-10-25
---

## Acceptance Criteria

- [ ] Inventory all date-related selectors, date computations, API date parameters, historical URL/deep-link contracts, chart scope, and duplicate code; document affected screens, preserved behavior, migration risk and actual implementation inventory in `artifacts/TIME-01-contract.md`.
- [ ] Specify one typed `DateRange` and independently selected `ComparisonRule`, including None, Previous month, Previous year and preceding equal-duration range; include no-comparison and custom-date UX, and preserve date-only posted-ledger semantics.
- [ ] Freeze explicit worked expected inclusive bounds for Current month/year, Last 30/365 days, and Custom From–To; use injected timezone-aware `today` in deterministic date helpers, not ad hoc browser UTC ISO date slicing.
- [ ] Decide and document month-end/leap-day clipping, equal-length vs calendar-aligned mapping, DST/local-time zone, missing historical coverage, invalid/future/unbounded dates, and comparison qualification when durations differ. For example Oct 5–15 vs Sep 5–15.
- [ ] Decide per-surface applicability and how to handle legacy 90d/YTD, last-month and All-time controls/URLs without breaking bookmarked queries, and distinguish selecting a preset from displaying the resulting actual From–To.
- [ ] Define API/backend ownership, performance limits and backward-compatibility expectations before tests are frozen; record exact success scenarios and exclusions.

## Technical Context / Test Plan

Suggested role: frontend/API contract architect. Existing duplicated logic is visible in `frontend/src/routes/transactions.tsx::presetBounds`, `spending.tsx::activePeriodBounds`, and `insights.tsx::periodBounds`; Spending has a calendar/rolling category comparison and Insights has 30/90/YTD. Inventory Overview, drilldowns and all other applicable date-filtered surfaces before coding.

## Execution Log

- 2026-10-25: Task specified from the accepted spending UX priorities. Not started; no failing-test baseline, production implementation, or independent verification claimed.
