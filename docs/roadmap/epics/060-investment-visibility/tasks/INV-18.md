---
id: INV-18
epic: 060-investment-visibility
title: Independently verify returns and performance presentation
status: todo
dependencies: ["INV-17"]
superseded_by: null
assigned_agent: null
created: 2026-11-10
---

## Acceptance Criteria

- [ ] Independently calculate expected money- and time-weighted results from literal fixtures and compare tolerances, including portfolio/subset boundaries, timed contributions and annualization.
- [ ] Exercise the actual UI for account/window switching, missing history, undefined returns and methodology/evidence inspection; confirm no fabricated precision or pooled average of account percentages.
- [ ] Rerun flow/gain and spending-isolation regressions; record M6 numerical/UI verdict with tested commit in artifacts/INV-18-verification.md.

## Technical Context / Test Plan

Read [the epic](../_epic.md) and [its spirit](../spirit.md). Preserve server-side investment/spending isolation throughout this task. Reuse existing project test directories and synthetic/redacted fixtures; put substantive reports in `artifacts/` prefixed `INV-18` and link them from this log when created. Implementation tasks consume frozen tests; verification tasks require a verifier other than the implementer and actual source-commit evidence.

## Execution Log

- 2026-11-10: Task specified for the staged investment-visibility epic. Not started; no implementation, provider validation, failing-test baseline or independent verification claimed.
