---
id: INV-09
epic: 060-investment-visibility
title: Independently verify the initial visibility milestone
status: in-progress
dependencies: ["INV-08"]
superseded_by: null
assigned_agent: independent-verifier
created: 2026-11-10
---

## Acceptance Criteria

- [ ] Verify actual responsive UI interactions and backend evidence for balances, holdings, filtered scope, observed history, freshness and missing data; record source commit and limitations.
- [ ] Confirm navigation has no lost review/net-worth workflow, count/drilldown parity remains intact, and investment-only data never appears on Spending.
- [ ] Issue an explicit M3 release verdict in artifacts/INV-09-verification.md; balances may ship independently of future contribution and return work.

## Technical Context / Test Plan

Read [the epic](../_epic.md) and [its spirit](../spirit.md). Preserve server-side investment/spending isolation throughout this task. Reuse existing project test directories and synthetic/redacted fixtures; put substantive reports in `artifacts/` prefixed `INV-09` and link them from this log when created. Implementation tasks consume frozen tests; verification tasks require a verifier other than the implementer and actual source-commit evidence.

## Execution Log

- 2026-11-10: Task specified for the staged investment-visibility epic. Not started; no implementation, provider validation, failing-test baseline or independent verification claimed.
- 2026-11-18: Independent verification started by independent-verifier on source `babdd3b` (`feat/investment-visibility`).
- 2026-11-18: Backend focused verification passed 47 tests across visibility, ingestion, ingestion regressions, isolation, review regressions, and spending accuracy invariants. Frontend production build emitted successfully; constrained Vitest and tsc exceeded the host memory limit. Source review found missing Investments UI filters/date/qualification disclosures and a tax-scope leak in the no-history fallback. See [INV-09 verification](../artifacts/INV-09-verification.md). Verdict: **NOT READY / FAIL**; task remains in-progress for implementation fixes and re-verification.
