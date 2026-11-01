---
id: INSP-03
epic: 030-inspectable-aggregates
title: Drill from month-over-month movers into current-period Activity
status: todo
dependencies: [INSP-01]
superseded_by: null
assigned_agent: null
created: 2026-09-08
---

## Acceptance Criteria

- [ ] Activating a Movers category opens Activity through the INSP-01 contract for
  that effective category and the displayed current comparison period.
- [ ] The default destination shows current-period transactions because they
  underlie the displayed `current` value; it does not combine current and previous
  rows or infer dates from the browser clock.
- [ ] Preserve source context identifying the Movers comparison and previous period
  so a later richer comparison view can build on it, without implementing that view
  now.
- [ ] The complete Activity population follows the same posted-spending, confirmed-
  transfer exclusion, refund, effective-category, and inclusive-date semantics as
  the mover calculation, and its signed expense contribution equals `current`.
- [ ] Categories with a nonzero change but zero current value lead to a truthful
  empty current-period Activity scope while retaining the comparison context; the
  UI does not substitute previous-period rows silently.
- [ ] Bars/category labels are keyboard and pointer operable with accessible names
  that include enough category/current/change context, and existing tooltip,
  ordering, responsive height, and color meaning remain intact.
- [ ] Add component/route and backend population-parity tests covering increased,
  decreased, unchanged, refund-netted, zero-current, confirmed-transfer, pending,
  and clipped month-to-date cases; run frontend tests, typecheck, build, and focused
  backend tests.

## Technical Context

`frontend/src/components/finance/charts/MoversChart.tsx` is currently presentational
and has no click callback. `frontend/src/routes/insights.tsx` fetches Movers without
parameters and shows the response month labels. The server response from
`analytics_category_movers()` includes `reporting.current_period` and
`previous_period` with precise bounds, but `getCategoryMovers()` and the
`CategoryMovers` frontend type currently discard that metadata. Preserve and use
the server bounds rather than reconstructing a whole calendar month from the label.

Suggested role: frontend visualization/API engineer with accounting-test review.

## Execution Log

- 2026-09-08: Task created after confirming the API already returns precise bounds
  that the frontend adapter currently drops; blocked on INSP-01.
