---
id: TIME-02
epic: 050-shared-date-range-semantics
title: Pin shared date bounds and comparison mapping with failing unit/API tests
status: todo
dependencies: [TIME-01]
superseded_by: null
assigned_agent: null
created: 2026-10-25
---

## Acceptance Criteria

- [ ] Write frozen RED tests against absent unified range/comparison abstraction, recording exact failure output and baseline commit in `artifacts/TIME-02-date-contract-tdd.md`; test authors must not implement TIME-03.
- [ ] Use literal tables for month/year to date, 30- and 365-day inclusive lengths, custom endpoints, prior month/year mappings, preceding adjacent window, none, and actual readable resulting date labels.
- [ ] Test Jan 31, February 28/29, leap/nonleap, Dec–Jan rollover, DST, timezone boundary near UTC midnight, end-before-start, date range with no history, and injected clock independence.
- [ ] Test that comparison is optional, not inferred from range or forced for custom dates, and explicit mapping does not silently equate unequal coverage/partial dates.
- [ ] Pin identical semantics at backend request serialization and frontend selector/formatter boundary, with no monetary math in browser; freeze oracle once reviewed.

## Technical Context / Test Plan

Suggested role: date-domain test author. Test helper pure inputs, injected today/zone, and API mapping; expected values should be literals. Run `npm run test` or targeted Vitest plus focused pytest if backend changes are required; record red command/commit.

## Execution Log

- 2026-10-25: Task specified from the accepted spending UX priorities. Not started; no failing-test baseline, production implementation, or independent verification claimed.
