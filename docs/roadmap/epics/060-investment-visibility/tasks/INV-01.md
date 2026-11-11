---
id: INV-01
epic: 060-investment-visibility
title: Validate Schwab and Fidelity investment coverage
status: todo
dependencies: []
superseded_by: null
assigned_agent: null
created: 2026-11-10
---

## Acceptance Criteria

- [ ] Inventory actual integration paths and capture a dated provider/account coverage matrix in artifacts/INV-01-coverage.md: taxable brokerage, traditional IRA, Roth, and workplace/NetBenefits separately; distinguish documented, tested, unsupported and awaiting access.
- [ ] Validate Investments entitlements, OAuth/link setup, billing/refresh options, available fields, pagination, correction behavior, freshness and actual history depth. Do not treat retail access as proof of workplace coverage.
- [ ] Use supported authorized access and synthetic/redacted examples; record unavailable access as a blocker, not a successful test. Do not remove/relink existing accounts or enable paid products merely to complete this research.
- [ ] Document current balance/snapshot reuse, transactions-coupled sync, mixed-product Items, and a feasible minimum milestone with explicit provider blockers and fallback options.

## Technical Context / Test Plan

Read [the epic](../_epic.md) and [its spirit](../spirit.md). Preserve server-side investment/spending isolation throughout this task. Reuse existing project test directories and synthetic/redacted fixtures; put substantive reports in `artifacts/` prefixed `INV-01` and link them from this log when created. Implementation tasks consume frozen tests; verification tasks require a verifier other than the implementer and actual source-commit evidence.

## Execution Log

- 2026-11-10: Task specified for the staged investment-visibility epic. Not started; no implementation, provider validation, failing-test baseline or independent verification claimed.
