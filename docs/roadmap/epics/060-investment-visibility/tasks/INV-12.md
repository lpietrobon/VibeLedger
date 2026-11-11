---
id: INV-12
epic: 060-investment-visibility
title: Independently verify flows and dollar performance
status: todo
dependencies: ["INV-11"]
superseded_by: null
assigned_agent: null
created: 2026-11-10
---

## Acceptance Criteria

- [ ] Independently reconcile literal fixture balances/flows/gain across individual, subset and pooled account views; verify corrected flows and in-kind/rollover semantics.
- [ ] Exercise actual chart filters and evidence drilldowns, including missing opening history and unresolved transfer cases; verify displayed gaps and qualified/withheld gain.
- [ ] Rerun spending isolation contracts and record M4 verdict, commands and tested commit in artifacts/INV-12-verification.md.

## Technical Context / Test Plan

Read [the epic](../_epic.md) and [its spirit](../spirit.md). Preserve server-side investment/spending isolation throughout this task. Reuse existing project test directories and synthetic/redacted fixtures; put substantive reports in `artifacts/` prefixed `INV-12` and link them from this log when created. Implementation tasks consume frozen tests; verification tasks require a verifier other than the implementer and actual source-commit evidence.

## Execution Log

- 2026-11-10: Task specified for the staged investment-visibility epic. Not started; no implementation, provider validation, failing-test baseline or independent verification claimed.
