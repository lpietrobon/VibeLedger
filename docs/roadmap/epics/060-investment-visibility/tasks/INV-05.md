---
id: INV-05
epic: 060-investment-visibility
title: Independently verify ingestion and spending isolation
status: todo
dependencies: ["INV-04"]
superseded_by: null
assigned_agent: null
created: 2026-11-10
---

## Acceptance Criteria

- [ ] An independent verifier runs frozen contracts against the actual backend and persisted fixtures, checks migration/retry/relink behavior, and records commit and commands in artifacts/INV-05-verification.md.
- [ ] Prove investment ingestion does not alter unrelated spending/income/recurring totals or leak into default Activity; explain only deliberate reconciled funding-transfer corrections with exact source evidence.
- [ ] Confirm investments-only success, mixed-product partial failure handling, stale/missing disclosures and net-worth single counting; unresolved failures block the visibility release.

## Technical Context / Test Plan

Read [the epic](../_epic.md) and [its spirit](../spirit.md). Preserve server-side investment/spending isolation throughout this task. Reuse existing project test directories and synthetic/redacted fixtures; put substantive reports in `artifacts/` prefixed `INV-05` and link them from this log when created. Implementation tasks consume frozen tests; verification tasks require a verifier other than the implementer and actual source-commit evidence.

## Execution Log

- 2026-11-10: Task specified for the staged investment-visibility epic. Not started; no implementation, provider validation, failing-test baseline or independent verification claimed.
