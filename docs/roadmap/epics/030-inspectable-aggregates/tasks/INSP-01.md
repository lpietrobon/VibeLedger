---
id: INSP-01
epic: 030-inspectable-aggregates
title: Establish the shared spending-category drilldown contract
status: todo
dependencies: [PI-14]
superseded_by: null
assigned_agent: null
created: 2026-09-08
---

## Acceptance Criteria

- [ ] Document and reuse one small contract for “inspect effective category X from
  inclusive date A through B under posted-spending semantics,” building on PI-02's
  Overview/Spending path rather than adding screen-specific URL construction.
- [ ] The contract defines canonical parameter names, base-path handling, exact
  versus parent-category behavior, posting/refund/transfer semantics, date
  inclusivity, stable sort, and how Activity communicates the active scope.
- [ ] Activity hydrates every contract field and sends the corresponding server-side
  request; filtering is not limited to the first fetched page or reproduced only in
  client memory.
- [ ] The helper accepts server-supplied reporting bounds and does not independently
  choose “today.” Source screens remain responsible for selecting the aggregate's
  real period.
- [ ] Preserve optional source context sufficient to identify the originating view
  and current-versus-comparison interpretation without making Activity dependent on
  a generic scope framework.
- [ ] Contract tests use a hand-checkable fixture with charges, category-netted
  refunds, pending rows, unconfirmed candidates, confirmed transfers, and more than
  one page of evidence; the destination's signed expense sum equals the source
  category amount.
- [ ] Add focused helper, route-hydration, and API evidence tests and run relevant
  frontend/backend suites, typecheck, and build.

## Technical Context

PI-02 starts from `CategoryComparison` and the local `appHref()` callbacks in
Overview/Spending. Activity currently reads `category`, `query`, `startDate`,
`endDate`, `sort`, and `order` from `window.location.search`; the backend category
parameter is exact while search-grammar `category:` supports parent matching. The
existing `is:spend` path in `app/api/routes.py` uses shared posted activity and
`expense_amount() != 0`. Prefer a typed shared helper in a small frontend library
module unless evidence requires a modest API extension.

Suggested role: frontend/API contract engineer with accounting-test review.

## Execution Log

- 2026-09-08: Task created; blocked on PI-02's initial shared drilldown path.
