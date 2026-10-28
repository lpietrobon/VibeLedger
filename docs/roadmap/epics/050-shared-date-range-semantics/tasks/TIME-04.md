---
id: TIME-04
epic: 050-shared-date-range-semantics
title: Pin cross-screen period-selection and monetary-parity behavior with failing integration tests
status: todo
dependencies: [TIME-01, TIME-02]
superseded_by: null
assigned_agent: null
created: 2026-10-25
---

## Acceptance Criteria

- [ ] Before routing integration, write frozen RED tests exercising identical range selections and comparison rules across applicable date-filtered Overview, Spending, Insights, Transactions/Activity, and other screens enumerated by TIME-01.
- [ ] Test that selected inclusive From–To bounds drive every corresponding KPI, time-series point, category comparison, Sankey if explicitly date-filtered, evidence query and drilldown; no stale or separately calculated period.
- [ ] Use literal ledger fixtures with posted/pending, category-netted refunds, confirmed/unconfirmed transfers, duplicates, and pagination beyond first response limit; verify chart totals equal complete underlying evidence.
- [ ] Test preserving custom URLs, refresh/back, an old deep-link, invalid input, unavailable comparable history, custom range without comparison, historical selection, and mobile/keyboard controls.
- [ ] Assert relevant page behavior remains coherent even when some analytics endpoints historically only accepted granularity; document every required API migration and freeze tests for TIME-05.

## Technical Context / Test Plan

Suggested role: integration test author separate from TIME-05 implementer. Stub endpoints only for control-flow tests; add focused backend population-parity integration tests for actual numbers. Save red baseline artifact `artifacts/TIME-04-cross-screen-tdd.md`.

## Execution Log

- 2026-10-25: Task specified from the accepted spending UX priorities. Not started; no failing-test baseline, production implementation, or independent verification claimed.
