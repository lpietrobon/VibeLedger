---
id: INV-15
epic: 060-investment-visibility
title: Independently verify pooled allocation
status: todo
dependencies: ["INV-14"]
superseded_by: null
assigned_agent: null
created: 2026-11-10
---

## Acceptance Criteria

- [ ] Independently recompute synthetic allocation amounts and denominators for direct securities, mixed funds, unknowns and selected account subsets.
- [ ] Exercise actual override/edit/sync and drilldown workflows; verify source/date disclosures, missing-value handling and unchanged spending.
- [ ] Record M5 verdict, tested commit and evidence in artifacts/INV-15-verification.md.

## Technical Context / Test Plan

Read [the epic](../_epic.md) and [its spirit](../spirit.md). Preserve server-side investment/spending isolation throughout this task. Reuse existing project test directories and synthetic/redacted fixtures; put substantive reports in `artifacts/` prefixed `INV-15` and link them from this log when created. Implementation tasks consume frozen tests; verification tasks require a verifier other than the implementer and actual source-commit evidence.

## Execution Log

- 2026-11-10: Task specified for the staged investment-visibility epic. Not started; no implementation, provider validation, failing-test baseline or independent verification claimed.
