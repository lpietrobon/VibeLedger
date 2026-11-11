---
id: INV-11
epic: 060-investment-visibility
title: Implement reconciled flows and contribution-versus-growth charts
status: todo
dependencies: ["INV-10"]
superseded_by: null
assigned_agent: null
created: 2026-11-10
---

## Acceptance Criteria

- [ ] Implement deterministic flow classification and durable review/correction, recalculating internal versus external flow for the actual selected account set.
- [ ] Compute opening + deposits - withdrawals + gain = ending with auditable source events, clear quality states and no double counting of transfer legs, trades or reinvestment.
- [ ] Build value/capital lines and separate gross deposit/withdrawal chart plus value, net-added and dollar-gain summaries. Label gain as total investment gain, not pure price appreciation.
- [ ] Pass frozen contracts and keep bank funding evidence accessible without polluting household spending or silently hiding uncertain bank payments.

## Technical Context / Test Plan

Read [the epic](../_epic.md) and [its spirit](../spirit.md). Preserve server-side investment/spending isolation throughout this task. Reuse existing project test directories and synthetic/redacted fixtures; put substantive reports in `artifacts/` prefixed `INV-11` and link them from this log when created. Implementation tasks consume frozen tests; verification tasks require a verifier other than the implementer and actual source-commit evidence.

## Execution Log

- 2026-11-10: Task specified for the staged investment-visibility epic. Not started; no implementation, provider validation, failing-test baseline or independent verification claimed.
