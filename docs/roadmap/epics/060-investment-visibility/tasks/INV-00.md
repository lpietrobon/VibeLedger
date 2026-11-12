---
id: INV-00
epic: 060-investment-visibility
title: Isolate spending before existing-item investment consent
status: in-progress
dependencies: []
superseded_by: null
assigned_agent: codex
created: 2026-11-11
---

## Acceptance Criteria

- [ ] Account-level bank ingestion and canonical reporting exclude investment and unclassified accounts, including legacy rows and include-transfers requests.
- [ ] Preserve source rows and balances; retain bank-side evidence; preserve confirmed funding reconciliation while excluding provisional cross-domain matches.
- [ ] Regression tests cover mixed sync, historical sync, unknown classification, direct API parity, SQL view, and unaffected bank behavior.
- [ ] Record release evidence and deployment/rollback procedure before enabling consent.

## Execution Log

- 2026-11-11: Extracted prerequisite from INV-01 release boundary under owner's explicit continuation. No live coverage completion claimed. Initial red baseline: three failures, mixed/historical sync imported two rows instead of one and Activity returned two instead of one. Building account-level allowlist (depository/credit/loan/payment), preserving source records and excluding unknown classification. Existing bank fixtures now explicitly state depository type rather than relying on missing classification.
- 2026-11-11: Full backend regression 367 passed (two pre-existing warnings); final expanded isolation suite 11 passed, including two subsequently added rollback cases. Roadmap scan 6 epics/80 tasks/0 issues; whitespace check clean. Existing financial oracles unchanged. See [isolation contract and release procedure](../artifacts/INV-00-isolation.md). Deployment verification pending.
