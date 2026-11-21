---
id: TIME-02
epic: 050-shared-date-range-semantics
title: Pin shared date bounds and comparison mapping with failing unit/API tests
status: done
dependencies: [TIME-01]
superseded_by: null
assigned_agent: time_contract_tests
created: 2026-10-25
---

## Acceptance Criteria

- [x] Write frozen RED tests against absent unified range/comparison abstraction, recording exact failure output and baseline commit in `artifacts/TIME-02-date-contract-tdd.md`; test authors must not implement TIME-03.
- [x] Use literal tables for month/year to date, 30- and 365-day inclusive lengths, custom endpoints, prior month/year mappings, preceding adjacent window, none, and actual readable resulting date labels.
- [x] Test Jan 31, February 28/29, leap/nonleap, Dec–Jan rollover, DST, timezone boundary near UTC midnight, end-before-start, date range with no history, and injected clock independence.
- [x] Test that comparison is optional, not inferred from range or forced for custom dates, and explicit mapping does not silently equate unequal coverage/partial dates.
- [x] Pin identical semantics at backend request serialization and frontend selector/formatter boundary, with no monetary math in browser; freeze oracle once reviewed.

## Technical Context / Test Plan

Suggested role: date-domain test author. Test helper pure inputs, injected today/zone, and API mapping; expected values should be literals. Run `npm run test` or targeted Vitest plus focused pytest if backend changes are required; record red command/commit.

## Execution Log

- 2026-10-25: Task specified from the accepted spending UX priorities. Not started; no failing-test baseline, production implementation, or independent verification claimed.

- 2026-11-16: Independent test author froze [36-case RED baseline](../artifacts/TIME-02-date-contract-tdd.md) against 4ba04b6: 15 expected failures, 21 passes; exact output retained. Literal unit, selector and HTTP serialization tests; legacy oracle migration documented before implementation. No application code changed. TIME-03 implementation belongs to a different agent.
