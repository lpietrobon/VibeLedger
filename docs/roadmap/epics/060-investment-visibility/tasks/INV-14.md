---
id: INV-14
epic: 060-investment-visibility
title: Implement editable pooled allocation
status: todo
dependencies: ["INV-13"]
superseded_by: null
assigned_agent: null
created: 2026-11-10
---

## Acceptance Criteria

- [ ] Implement value-weighted exposure across selected holdings, editable fund splits, provenance dates and durable overrides; do not classify ETFs/mutual funds as stock merely by instrument type.
- [ ] Build a simple allocation bar/table with drilldowns to contributing holdings/accounts and explicit unknown/incomplete coverage; avoid double counting fund and underlying exposures.
- [ ] Pass frozen contracts without introducing automated look-through feeds, advice or trading features.

## Technical Context / Test Plan

Read [the epic](../_epic.md) and [its spirit](../spirit.md). Preserve server-side investment/spending isolation throughout this task. Reuse existing project test directories and synthetic/redacted fixtures; put substantive reports in `artifacts/` prefixed `INV-14` and link them from this log when created. Implementation tasks consume frozen tests; verification tasks require a verifier other than the implementer and actual source-commit evidence.

## Execution Log

- 2026-11-10: Task specified for the staged investment-visibility epic. Not started; no implementation, provider validation, failing-test baseline or independent verification claimed.
