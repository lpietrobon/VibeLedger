---
id: INV-02
epic: 060-investment-visibility
title: Freeze investment domain and accounting boundaries
status: todo
dependencies: ["INV-01"]
superseded_by: null
assigned_agent: null
created: 2026-11-10
---

## Acceptance Criteria

- [ ] Publish artifacts/INV-02-contract.md covering dedicated tables/services/endpoints, account-level domain/tax classification, security identity, valuation provenance and boundary between investment activity and the canonical spending ledger.
- [ ] Inventory all spending, income/cashflow, recurring, category/merchant, Activity, export and transfer-query consumers. Specify server-side isolation, including legacy investment rows and include-transfers behavior; unknown/mixed account types require explicit treatment.
- [ ] Freeze literal accounting examples for checking funding, withdrawal, internal cross-broker transfers, trades, reinvestment, fees, sweeps, in-kind transfers, retirement rollovers and unresolved counterparties. Preserve bank-side evidence without institution-name-based exclusions.
- [ ] Define net-worth single counting, account removal/relink lifecycle, deduplication, manual correction provenance, account closure, unsupported currencies and stale/missing valuation policies. Distinguish tax-year contributions from portfolio flows.

## Technical Context / Test Plan

Read [the epic](../_epic.md) and [its spirit](../spirit.md). Preserve server-side investment/spending isolation throughout this task. Reuse existing project test directories and synthetic/redacted fixtures; put substantive reports in `artifacts/` prefixed `INV-02` and link them from this log when created. Implementation tasks consume frozen tests; verification tasks require a verifier other than the implementer and actual source-commit evidence.

## Execution Log

- 2026-11-10: Task specified for the staged investment-visibility epic. Not started; no implementation, provider validation, failing-test baseline or independent verification claimed.
