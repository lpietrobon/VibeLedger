---
id: INSP-04
epic: 030-inspectable-aggregates
title: Independently verify aggregate-to-Activity parity
status: todo
dependencies: [INSP-02, INSP-03]
superseded_by: null
assigned_agent: null
created: 2026-09-08
---

## Acceptance Criteria

- [ ] A verifier other than the drilldown implementers evaluates an identified
  integrated commit and independently derives expected transaction populations and
  signed totals from a hand-checkable synthetic ledger.
- [ ] Verify Overview, Spending, every supported Sankey period, and Movers all use
  the shared contract and reproduce the source aggregate's current transaction set,
  including evidence beyond the first response page.
- [ ] Challenge exact/parent categories, same names, category-netted refunds,
  refund-only/zero-current Movers cases, pending rows, confirmed transfers,
  unresolved candidates, month/year boundaries, and clipped current periods.
- [ ] Verify destination scope visibility, back/forward/reload behavior, base-path
  correctness, empty/error states, and keyboard/pointer use at wide and narrow
  layouts; navigation alone is not acceptance evidence.
- [ ] Confirm no client independently reimplements monetary calculations and no
  generic scope framework or agent infrastructure was introduced without a repeated
  demonstrated need.
- [ ] Run complete backend/frontend checks, typecheck, build, and comparable coverage
  reporting; record commands, expected/actual results, commit, and limitations.
- [ ] Reverify material fixes, regenerate roadmap indexes, and close the epic only
  when all drilldowns agree with their aggregates.

## Technical Context

Suggested role: independent accounting/product QA. Reuse fixture setup where useful,
but write literal expected row IDs and signed totals without calling production
aggregation code as the oracle. Save the report under
`artifacts/INSP-04-independent-verification.md` and link it here.

## Execution Log

- 2026-09-08: Task created; blocked on Sankey and Movers drilldown implementation.
