---
id: INV-00
epic: 060-investment-visibility
title: Isolate spending before existing-item investment consent
status: done
dependencies: []
superseded_by: null
assigned_agent: codex
created: 2026-11-11
---

## Acceptance Criteria

- [x] Account-level bank ingestion and canonical reporting exclude investment and unclassified accounts, including legacy rows and include-transfers requests.
- [x] Preserve source rows and balances; retain bank-side evidence; preserve confirmed funding reconciliation while excluding provisional cross-domain matches.
- [x] Regression tests cover mixed sync, historical sync, unknown classification, direct API parity, SQL view, and unaffected bank behavior.
- [x] Record release evidence and deployment/rollback procedure before enabling consent.

## Execution Log

- 2026-11-11: Extracted prerequisite from INV-01 release boundary under owner's explicit continuation. No live coverage completion claimed. Initial red baseline: three failures, mixed/historical sync imported two rows instead of one and Activity returned two instead of one. Building account-level allowlist (depository/credit/loan/payment), preserving source records and excluding unknown classification. Existing bank fixtures now explicitly state depository type rather than relying on missing classification.
- 2026-11-11: Full backend regression 367 passed (two pre-existing warnings); final expanded isolation suite 11 passed, including two subsequently added rollback cases. Roadmap scan 6 epics/80 tasks/0 issues; whitespace check clean. Existing financial oracles unchanged. See [isolation contract and release procedure](../artifacts/INV-00-isolation.md). Deployment verification pending.
- 2026-11-13 status checkpoint: Deployment checkout is at source `4d2e2f1`; API and frontend services active. Original deployment doctor failed during frontend startup (connection refused / HTTP 502). Fresh deployment doctor now passes local and external configuration/health checks. Before/after hashes match for 6 of 7 bank endpoints; `/analytics/overview` differs and remains to be investigated (comparison spans reporting dates; no cause asserted). Investment linking remains disabled; no consent session or holdings ingestion completed. Local institution names are null, so Schwab identification must use provider metadata rather than name filtering. Live consent/browser completion remains unverified.

- 2026-11-13: Resolved Overview mismatch: current deployed response with reporting_date=2026-11-11 exactly matches the saved predeployment SHA-256. All seven bank endpoint comparisons pass when reporting date is held constant. Deployment doctor passes. Source deployed: `4d2e2f1`. Backed up and merged host env to enable only investment Link; scheduled sync remains off. Provider metadata confirms local Item 2 is Charles Schwab (local institution names were null). Existing-Item update consent session created successfully; configured tailnet Connect URL returned HTTP 200 with Plaid handler. No holdings calls or replacement Item/token exchange. User browser rendering/OAuth/account selection and provider-confirmed consent remain pending under INV-01; bearer URL retained only in private handoff, not project docs.
