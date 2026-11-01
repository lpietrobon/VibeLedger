---
id: TIME-06
epic: 050-shared-date-range-semantics
title: Independently verify date-selection consistency and source evidence
status: todo
dependencies: [TIME-05]
superseded_by: null
assigned_agent: null
created: 2026-10-25
---

## Acceptance Criteria

- [ ] Independent verifier checks identified integrated revision, derives literal expected from/to and comparison windows, and demonstrates same behavior on all TIME-01 enumerated applicable views.
- [ ] Test all five presets, custom from/to everywhere, None/previous month/previous year/preceding equal-length comparisons, and visibly rendered actual mapped ranges including clipping/partial-data qualification.
- [ ] Verify timezone/DST/Jan-Feb leap/month-end boundaries and histories without comparable data; no off-by-one, no browser/UTC day drift, no silently changed past deep-links.
- [ ] Verify backend aggregation and complete paginated Activity evidence agree for charges, refunds, transfers, pending, duplicates, and arbitrary custom date windows.
- [ ] Assess UI on narrow/wide screens, touch/keyboard, back/forward/refresh, sync freshness, performance, and coexistence with any timeline spike drilldowns.
- [ ] Run full relevant pytest, Vitest, typecheck, build and coverage comparison; save actual commands, SHA, failures/fixes and independent report `artifacts/TIME-06-verification.md`. Regenerate roadmap indexes before closing.

## Technical Context / Test Plan

Suggested role: independent accounting/product QA. Verifier may repair app code but must not rewrite frozen test oracles without explicit approved revision.

## Execution Log

- 2026-10-25: Task specified from the accepted spending UX priorities. Not started; no failing-test baseline, production implementation, or independent verification claimed.
