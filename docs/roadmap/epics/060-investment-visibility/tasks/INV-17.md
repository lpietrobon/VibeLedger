---
id: INV-17
epic: 060-investment-visibility
title: Implement qualified money-weighted and time-weighted returns
status: todo
dependencies: ["INV-16"]
superseded_by: null
assigned_agent: null
created: 2026-11-10
---

## Acceptance Criteria

- [ ] Implement backend calculations to the frozen numerical oracle, reusing reconciled flows, snapshots, account scopes and shared date bounds; recompute affected results after supported corrections.
- [ ] Default to personal money-weighted return with clearly labeled time-weighted detail; show dollar gain alongside, not as a substitute for the return definition.
- [ ] Display period/annualized labels, exact range, coverage and method. Withhold unsupported/ambiguous results with a concise reason; do not reconstruct imaginary daily history or silently substitute a different method.
- [ ] Pass numerical and interaction contracts with inspectable calculation inputs; benchmark comparison and extensive historical price backfill remain deferred.

## Technical Context / Test Plan

Read [the epic](../_epic.md) and [its spirit](../spirit.md). Preserve server-side investment/spending isolation throughout this task. Reuse existing project test directories and synthetic/redacted fixtures; put substantive reports in `artifacts/` prefixed `INV-17` and link them from this log when created. Implementation tasks consume frozen tests; verification tasks require a verifier other than the implementer and actual source-commit evidence.

## Execution Log

- 2026-11-10: Task specified for the staged investment-visibility epic. Not started; no implementation, provider validation, failing-test baseline or independent verification claimed.
