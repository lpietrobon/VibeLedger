---
id: INSP-02
epic: 030-inspectable-aggregates
title: Drill from expanded Sankey categories into Activity
status: todo
dependencies: [INSP-01]
superseded_by: null
assigned_agent: null
created: 2026-09-08
---

## Acceptance Criteria

- [ ] When a spending bucket is expanded, each visible leaf category is clearly
  interactive and opens Activity through the shared INSP-01 contract.
- [ ] The destination carries the exact effective category and the selected Sankey
  period's inclusive start/end dates for 30d, 90d, and YTD rather than the page's
  default or a newly computed period.
- [ ] The complete Activity population uses the same posted-spending, confirmed-
  transfer exclusion, effective-category, and refund-netting semantics as the
  clicked Sankey category; its signed expense contribution equals the visible link.
- [ ] Unconfirmed transfer candidates remain counted and visible; confirmed
  transfers, pending rows, out-of-period rows, and sibling categories are absent.
- [ ] Expanded/collapsed behavior remains intact, bucket nodes still expand rather
  than navigate, and category activation works by keyboard and pointer with an
  understandable accessible name.
- [ ] A source inspection checkpoint confirms the clean existing path—category keys
  on expanded nodes plus bounds in Insights—before refactoring. If a major chart
  rewrite is genuinely required, record why and implement the narrowest truthful
  alternative rather than a generic scope subsystem.
- [ ] Add component/route integration and backend population-parity tests for at
  least two categories, a netted refund, confirmed/unconfirmed transfers, and all
  supported periods; run frontend tests, typecheck, build, and focused backend tests.

## Technical Context

`SankeyChart.tsx::buildGraph` currently creates expanded leaves with stable
`cat:${category}` keys and `expandable: false`; only income/bucket nodes are
clickable through `onToggle`. `frontend/src/routes/insights.tsx` computes and passes
the exact selected Sankey bounds to `getCashflowSankey`. Extend the node event model
without conflating category inspection with bucket expansion. The backend payload's
positive category amount is the sum of shared signed `expense_amount()` for that
effective category, so Activity must include contributing refund rows as well as
charges.

Suggested role: frontend visualization engineer paired with accounting QA.

## Execution Log

- 2026-09-08: Task created after confirming expanded category keys and selected
  period bounds already exist; blocked on the shared drilldown contract. Coordinate
  implementation with PI-10 because both tasks touch the Sankey component.
