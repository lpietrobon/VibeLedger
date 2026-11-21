---
id: INV-03
epic: 060-investment-visibility
title: Pin ingestion and spending-isolation regression contracts
status: done
dependencies: ["INV-02"]
superseded_by: null
assigned_agent: codex
created: 2026-11-10
---

## Acceptance Criteria

- [x] Add failing tests in existing test directories for investment-only and mixed-product sync, pagination/retry/corrections, idempotent holdings/activity and snapshot persistence, and bank sync continuing after investment errors.
- [x] Pin before/after spending, operating-income/cashflow, recurring, category, merchant and default Activity expectations after ingesting representative investment events; include direct API calls and include-transfers options.
- [x] Pin account-level cash-management classification, legacy-data handling, net-worth single counting, stale versus missing data and cross-domain evidence lifecycle. Record red commands and literal expected values before implementation.

## Technical Context / Test Plan

Read [the epic](../_epic.md) and [its spirit](../spirit.md). Preserve server-side investment/spending isolation throughout this task. Reuse existing project test directories and synthetic/redacted fixtures; put substantive reports in `artifacts/` prefixed `INV-03` and link them from this log when created. Implementation tasks consume frozen tests; verification tasks require a verifier other than the implementer and actual source-commit evidence.

## Execution Log

- 2026-11-10: Task specified for the staged investment-visibility epic. Not started; no implementation, provider validation, failing-test baseline or independent verification claimed.

- 2026-11-15: Started test-first ingestion slice against INV-02 contract. No implementation yet.

- 2026-11-15: Frozen `tests/test_investment_ingestion.py`: 20 expected failing tests before implementation (missing models/service/adapter/route). Command: `python -m pytest tests/test_investment_ingestion.py -q`. Literal bank expense 25, investment balance 1250, holdings 1200; expected net worth 1350 with bank balance 100, never 2550. Replays/corrections/partial failure, account domain, unsupported values, window reconciliation, pagination and release gate covered. Existing INV-00 isolation tests retained.
