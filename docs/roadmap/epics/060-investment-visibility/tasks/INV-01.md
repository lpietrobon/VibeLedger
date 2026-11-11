---
id: INV-01
epic: 060-investment-visibility
title: Validate Schwab and Fidelity investment coverage
status: in-progress
dependencies: []
superseded_by: null
assigned_agent: codex
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

- 2026-11-10: Started on `feat/investment-visibility`, based on roadmap commit `86238d4` and canonical main `ec2a3ac`, in an isolated worktree. Building a read-only readiness probe before any investment activation or ingestion.
- 2026-11-10: Implemented diagnostic in source commit `2b1d2c2`. [Coverage report and remaining gates](../artifacts/INV-01-coverage.md) records the integration audit, Link requirements, coverage matrix and limitations. Red baseline: 7 expected missing-method failures. Targeted green: `python -m pytest tests/test_investment_readiness.py tests/test_plaid_client.py -q`, 12 passed. No production provider call or independent-verification claim; task remains in progress.
- 2026-11-10: Full backend regression on source `2b1d2c2`: `python -m pytest -q` — 345 passed, 2 warnings (Starlette httpx deprecation; SQLAlchemy identity-map warning). Roadmap scan: 6 epics, 79 tasks, 0 issues. No deployment.

- 2026-11-10: Ran authorized Production metadata checks from source `0163478` without writes or product activation. Resolved an existing Schwab Item exposing checking only: Investments available=true, billed=false, consented=false. No Fidelity Item found. Recorded redacted evidence and next consent/entitlement gates in [coverage report](../artifacts/INV-01-coverage.md). Holdings/activity and account-class coverage remain unverified; INV-01 stays in progress.
