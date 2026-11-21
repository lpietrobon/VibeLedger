---
id: INV-10
epic: 060-investment-visibility
title: Freeze contribution and investment-gain contracts with failing tests
status: todo
dependencies: ["INV-09"]
superseded_by: null
assigned_agent: null
created: 2026-11-10
---

## Acceptance Criteria

- [ ] Freeze flow-sign, effective-date, valuation-cutoff and selected-account-boundary rules in artifacts/INV-10-flow-contract.md, with auditable links between bank and investment evidence rather than duplicate ledger postings.
- [ ] Add literal fixtures: opening 1000, deposit 200, closing 1250 gives gain 50 and capital baseline 1200; opening 1000, withdrawal 100, closing 950 gives gain 50. Internal transfer gives zero pooled external flow but account-specific withdrawal/deposit.
- [ ] Cover trades, reinvested income, fees, sweeps, rollovers, in-kind transfer value, transfer-in-transit timing, duplicate/corrected events, uncertain counterparties and unsupported currency. Unreconciled residuals must not masquerade as market growth.
- [ ] Pin value versus opening-value-plus-cumulative-net-flow lines, gross monthly deposits/withdrawals, missing opening valuations and exact chart-to-evidence drilldowns. Record failing backend/UI tests.

## Technical Context / Test Plan

Read [the epic](../_epic.md) and [its spirit](../spirit.md). Preserve server-side investment/spending isolation throughout this task. Reuse existing project test directories and synthetic/redacted fixtures; put substantive reports in `artifacts/` prefixed `INV-10` and link them from this log when created. Implementation tasks consume frozen tests; verification tasks require a verifier other than the implementer and actual source-commit evidence.

## Execution Log

- 2026-11-10: Task specified for the staged investment-visibility epic. Not started; no implementation, provider validation, failing-test baseline or independent verification claimed.
