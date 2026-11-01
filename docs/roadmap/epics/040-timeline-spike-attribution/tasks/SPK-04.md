---
id: SPK-04
epic: 040-timeline-spike-attribution
title: Pin timeline tooltip and transaction drilldown with failing frontend tests
status: todo
dependencies: [SPK-01]
superseded_by: null
assigned_agent: null
created: 2026-10-25
---

## Acceptance Criteria

- [ ] Before implementing chart interaction, add frozen RED component/route/API-contract tests for keyboard/pointer activation of a temporal spike point and a clear, separate `Inspect transactions` action.
- [ ] Assert tooltip/notes expose date, observed total, baseline, positive excess, leading driver, amount and its share when available; qualified/no-spike/unknown cases must not assert spurious anomalies.
- [ ] Confirm clicking the point never accidentally navigates, cumulative plots use the corresponding interval contribution rather than cumulative total, and normal hover/selection and accessible labels remain intact.
- [ ] Pin exact source range and all-row posted-spend evidence scope into Activity using the INSP-01 contract or narrowest compatible extension; include refunds, more-than-one-page cases, and a noncategory all-spend point.
- [ ] Freeze UI/API tests for SPK-05; record failing tests/commit and literal expected navigation URL and screenshot/DOM state.

## Technical Context / Test Plan

Suggested role: frontend TDD engineer independent of SPK-05. Use existing React/Vitest test setup and chart fixtures. If INSP-01 only supports category scopes, formally specify a narrow all-spending date-point extension rather than abusing category filters.

## Execution Log

- 2026-10-25: Task specified from the accepted spending UX priorities. Not started; no failing-test baseline, production implementation, or independent verification claimed.
