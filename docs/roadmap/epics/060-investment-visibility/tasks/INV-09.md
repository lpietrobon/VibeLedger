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
- 2026-11-18: Follow-up independently verified source `8d66313` after native tax/account/date filters and the tax-scoped fallback amendment. The focused backend suite passed 47 tests and spending isolation remained clean. Rendered browser evidence was unavailable; frontend build, Vitest, and tsc were SIGTERM'd by the host memory limit. Source review found the date inputs omitted from the React Query key, so date changes do not reliably refetch. See [INV-09 verification](../artifacts/INV-09-verification.md). Explicit M3 verdict: **NOT READY / FAIL**; task remains in-progress.
- 2026-11-18: Final independent re-verification at `289e2d2` confirmed date values now participate in the query key and the backend suite remains 47 passed. Browser tooling remains unavailable and frontend checks remain memory-bound; explicit M3 verdict remains **NOT READY / FAIL**, task in-progress.
- 2026-11-18: Final independent re-verification of source `289e2d2` confirmed `startDate` and `endDate` are now included in the Investments React Query key. The shared-venv focused backend suite passed 47 tests; production build emitted successfully before post-build host-memory termination, while `tsc` was killed at the 502/512 MiB bound. Browser tooling remains unavailable, so rendered responsive interaction evidence is still absent. See [INV-09 verification](../artifacts/INV-09-verification.md). Explicit M3 verdict remains **NOT READY / FAIL**; task remains in-progress.
- 2026-11-20: Consolidated duplicate GitHub workflows into the existing authoritative `Tests` workflow. The frontend job uses Node 24 and runs `npm ci`, typecheck, the full Vitest suite, and the production build on each push/PR; successful builds retain `frontend-dist` for seven days. This moves memory-intensive gates off Homepi without weakening INV-09: rendered responsive interaction evidence is still required before the M3 verdict can change.
