---
id: 010-trustworthy-cashflow
title: Trustworthy cashflow across linked accounts
status: in-progress
owner: coordinator
created: 2026-09-02
revision: 1
---

## Goal

Make VibeLedger's existing income, spending, and cashflow reporting dependable as
more accounts are linked. The user should understand current versus previous
spending, explain changes, and resolve uncertainty without becoming the ledger's
full-time bookkeeper. [The spirit of this epic](spirit.md) is the durable statement
of intent; implementation choices may change while serving that intent.

## Scope Notes

Progress checkpoint: [recovered agent drafts, test evidence, and remaining gaps](artifacts/CF-01-recovered-progress.md).
Partial work is recorded in task logs; no application task has final acceptance.

- Prioritize correctness and clarity of existing functionality over new features.
  Focus on checking accounts, credit cards, and supported payment systems such as
  Venmo. All linked accounts define the reporting boundary, irrespective of owner
  or type; a linked investment account can be a transfer counterparty without
  introducing investment analysis.
- Use posting dates for realized activity. Count a credit-card purchase once;
  its repayment between linked accounts is internal. Established movements
  between linked accounts do not create income or expense. Boundary-crossing
  activity is external; preserve explicit refund treatment rather than calling
  every incoming amount earned income.
- Distinguish an imported copy of a transaction from two actual charges. Uncertain
  transfers or duplicate-charge candidates remain visible and counted until
  resolved; matching amount and date alone must not silently hide expenditure.
- Historical reports recompute when new accounts, history, or corrections improve
  reconciliation. Make period comparisons, simple categories, drill-downs,
  existing recurring summaries, and review outcomes agree about the same money.
- Lead with spending and its comparison; present uncertainty and data coverage
  as supporting context. An incomplete period must not masquerade as a complete
  comparison. Review should be selective and low effort.
- Keep calculations reproducible through shared functions and existing APIs;
  future agents should query summaries and supporting evidence. Keep maintenance
  proportional to a side project. Aim for roughly 70–80% meaningful backend test
  coverage, preserve any higher measured baseline, and separately verify critical
  frontend behavior. Define scope and measurement before enforcing a gate.
- Defer investment features, forecasting, optimization, new agent infrastructure,
  broad anomaly detection, document ingestion, and sophisticated reimbursement
  matching. Gross spending is acceptable where reimbursements cannot be reliably
  attributed. Validate existing refunds without requiring routine manual linking.
- Verify payment-provider support and account/history limitations before claiming
  coverage. This epic does not promise a new Venmo connector or currency-conversion
  system; unsupported cases need an explicit limitation and a separate decision.
- Deployment remains with the user. Earlier unpublished implementation drafts
  require inventory and verification before reuse; nothing is accepted by the
  creation of this roadmap.

## Revision Log

- rev 1 (2026-09-02): Pause the broader finance-intelligence feature backlog and
  establish a hardening epic around trustworthy existing cashflow reporting.
