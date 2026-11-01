---
id: TIME-03
epic: 050-shared-date-range-semantics
title: Implement shared date engine, typed selector and comparison adapter
status: todo
dependencies: [TIME-02]
superseded_by: null
assigned_agent: null
created: 2026-10-25
---

## Acceptance Criteria

- [ ] Make unchanged TIME-02 date mapping/validation/serialization tests GREEN using one reusable frontend range selection and date arithmetic module, with a canonical backend date contract rather than multiple page-specific algorithms.
- [ ] Expose five common presets including visible custom From–To, and optional separate comparison rule; preserve meaningful legacy All-time query filter and old deep-links without inventing dates.
- [ ] Use explicit day-count and timezone policies from TIME-01, round-trip selected bounds through UI labels and URLs, and show actual comparison dates and qualification for truncated/unequal ranges.
- [ ] Keep component and pure date helpers small, testable, keyboard/touch accessible; do not make every view share global state automatically or change accounting aggregation.
- [ ] Run targeted unit/API tests and frontend typecheck/build; document the shared API and any compatibility shims.

## Technical Context / Test Plan

Suggested role: frontend platform and API engineer. Consider `frontend/src/lib/dateRange.ts` and `frontend/src/components/finance/DateRangeSelector.tsx`, unless audit finds a smaller existing shared module.

## Execution Log

- 2026-10-25: Task specified from the accepted spending UX priorities. Not started; no failing-test baseline, production implementation, or independent verification claimed.
