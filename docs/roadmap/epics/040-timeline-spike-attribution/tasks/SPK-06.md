---
id: SPK-06
epic: 040-timeline-spike-attribution
title: Independently verify spike mathematics, usability and source-point parity
status: todo
dependencies: [SPK-05]
superseded_by: null
assigned_agent: null
created: 2026-10-25
---

## Acceptance Criteria

- [ ] Verifier different from SPK-02/03/04/05 implementers uses a fresh identified integrated commit and separately hand-computed synthetic ledger to check visible spike statements, baseline eligibility, percentages, ties, clipping, residuals and abstentions.
- [ ] Verify one-tap/one-action path from chart spike into the exact full Activity set, no separate date recreation, and equivalence of signed source-point and paginated evidence totals.
- [ ] Probe daily spend and cumulative delta, calendar boundaries, refunds, pending, duplicate corrections, confirmed transfers, no-history, zero/negative and recurring charges, and high-density time-series points.
- [ ] Verify mouse/touch/keyboard, narrow screen, focus, tooltip accessibility, navigation/back/refresh, and chart performance; confirm Sankey view remains unmodified.
- [ ] Run full relevant Python/frontend tests, typecheck, build and comparable coverage; record actual commands, pass/fail, known limitations and independent report `artifacts/SPK-06-verification.md`; recommend closure only on real evidence.

## Technical Context / Test Plan

Suggested role: independent QA reviewer. Do not copy implementation calculations into expected values. If implementation needs repair, never rewrite frozen TDD assertions without escalating scope/contract disagreement.

## Execution Log

- 2026-10-25: Task specified from the accepted spending UX priorities. Not started; no failing-test baseline, production implementation, or independent verification claimed.
