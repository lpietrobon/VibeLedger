---
id: INV-02
epic: 060-investment-visibility
title: Freeze investment domain and accounting boundaries
status: done
dependencies: ["INV-00"]
superseded_by: null
assigned_agent: codex
created: 2026-11-10
---

## Acceptance Criteria

- [x] Publish artifacts/INV-02-contract.md covering dedicated tables/services/endpoints, account-level domain/tax classification, security identity, valuation provenance and boundary between investment activity and the canonical spending ledger.
- [x] Inventory all spending, income/cashflow, recurring, category/merchant, Activity, export and transfer-query consumers. Specify server-side isolation, including legacy investment rows and include-transfers behavior; unknown/mixed account types require explicit treatment.
- [x] Freeze literal accounting examples for checking funding, withdrawal, internal cross-broker transfers, trades, reinvestment, fees, sweeps, in-kind transfers, retirement rollovers and unresolved counterparties. Preserve bank-side evidence without institution-name-based exclusions.
- [x] Define net-worth single counting, account removal/relink lifecycle, deduplication, manual correction provenance, account closure, unsupported currencies and stale/missing valuation policies. Distinguish tax-year contributions from portfolio flows.

## Technical Context / Test Plan

Read [the epic](../_epic.md) and [its spirit](../spirit.md). Preserve server-side investment/spending isolation throughout this task. Reuse existing project test directories and synthetic/redacted fixtures; put substantive reports in `artifacts/` prefixed `INV-02` and link them from this log when created. Implementation tasks consume frozen tests; verification tasks require a verifier other than the implementer and actual source-commit evidence.

## Execution Log

- 2026-11-10: Task specified for the staged investment-visibility epic. Not started; no implementation, provider validation, failing-test baseline or independent verification claimed.

- 2026-11-15: Published [frozen domain/accounting contract](../artifacts/INV-02-contract.md). Audited canonical consumers and existing removal/net-worth code. Live provider validation remains INV-01; fixture development proceeds from verified INV-00 isolation.
