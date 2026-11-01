---
id: TIME-05
epic: 050-shared-date-range-semantics
title: Integrate unified range selection across all applicable views
status: todo
dependencies: [TIME-03, TIME-04]
superseded_by: null
assigned_agent: null
created: 2026-10-25
---

## Acceptance Criteria

- [ ] Make unchanged TIME-04 integrated tests GREEN across actual date-filtered surfaces: reusable selector replaces repeated frontend preset date-math; every applicable chart and filtered Activity respects explicit selected start/end.
- [ ] Ensure optional comparison rule consistently maps custom or preset ranges to exact comparison bounds, with clear qualification and no comparison rendered when None is chosen or data are insufficient.
- [ ] Update backend analytics to accept explicit dates/comparison bounds as needed, retaining server-owned money math and existing shared posted transaction semantics; no client-side recomputation of totals.
- [ ] Preserve legacy deep-links and view-specific interaction states, keep existing Sankey functional but do not add spike detection to it, and avoid reimplementing `today` logic within pages.
- [ ] Check selected period across chart-to-Activity deep links and any timeline spike annotations if already delivered; align point periods with exact source selection.
- [ ] Run all relevant frontend/backend suites, frontend typecheck and production build. Record touched views, endpoints, performance, before/after API behavior and commit.

## Technical Context / Test Plan

Suggested role: frontend+API integrator. Incrementally switch each audited date-filtered surface instead of a big-bang UI redesign. Annotate any postponed surfaces with reason and a separate task; do not mark this done with missing applicable views.

## Execution Log

- 2026-10-25: Task specified from the accepted spending UX priorities. Not started; no failing-test baseline, production implementation, or independent verification claimed.
