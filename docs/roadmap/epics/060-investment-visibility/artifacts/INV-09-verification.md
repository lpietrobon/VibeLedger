# INV-09 independent verification — M3 investment visibility

**Verifier:** independent-verifier  
**Date:** 2026-11-18  
**Source:** feat/investment-visibility at babdd3b (Implement investment balances and holdings visibility)  
**Fixture policy:** synthetic test fixtures only; no personal holdings or credentials used.

## Commands and results

- Backend focused command: python -m pytest -q tests/test_investment_visibility_tdd.py tests/test_investment_ingestion.py tests/test_investment_ingestion_regressions.py tests/test_investment_isolation.py tests/test_investment_review_regressions.py tests/test_spending_accuracy_invariants.py
  - **47 passed**, 1 existing Starlette/httpx deprecation warning.
  - Covers summary totals, holdings/history, empty-vs-zero, exact bounds, ingestion, ingestion regressions, account isolation, review regressions, and spending accuracy/isolation invariants.
- npm run build in frontend
  - Vite transformed 2,496 modules and emitted the Investments chunk successfully; the wrapper was subsequently killed by the host memory limit after the successful build output.
- npm exec -- vitest run --pool=forks --no-file-parallelism --maxWorkers=1 src/routes/time04-cross-screen.test.tsx
  - Could not complete: host memory limit exceeded (579 MiB observed; 575 MiB limit).
- npm exec -- tsc --noEmit --pretty false
  - Could not complete: host memory limit exceeded (606 MiB observed; 574 MiB limit).
- Browser interaction evidence was unavailable: no browser-control tool was exposed in this verifier session. The production bundle and source inspection are the strongest rendered/source evidence available.

## Evidence reviewed

- frontend/src/routes/investments.tsx renders available/not-connected/empty/error states, total value, null gain, account rows, holdings table, observed history table, as-of/provenance, and accessible table captions.
- frontend/src/App.tsx maps both /investments and compatibility /overview to Investments; / remains Spending.
- frontend/src/components/layout/AppShell.tsx includes Investments navigation while retaining Spending, Recurring, Transactions, Accounts, and More.
- app/services/investment_sync.py computes server-side totals, scoped holdings/history, freshness, coverage, observed provenance, and null gain.
- app/api/routes.py accepts exact ordered bounds, repeated account_ids, and all|taxable|tax-deferred|roth filters.

## Findings

### Release-blocking

1. **UI does not implement the frozen filter/date contract.** InvestmentsPage calls getInvestmentSummary() with no account IDs, tax filter, or date bounds and renders no account/tax selector or shared date selector. The API supports these parameters, but a user cannot exercise them from the route.
2. **UI omits required qualification disclosures.** The page shows as-of/provenance and per-account freshness/coverage, but does not show effective_range, history_coverage, duplicate_account_coverage, currency qualification, or exact first/last observed bounds. This prevents the required visible completeness/coverage interpretation.
3. **Backend fallback can violate selected scope.** In app/services/investment_sync.py, when a requested range produces no history, the fallback loops over query.all() without reapplying tax_matches; a scoped tax-filter request can therefore append latest history from accounts outside the selected tax scope. Add a regression test and apply the same scope to the fallback before release.

### Passed

- Null gain is preserved as unavailable, not zero.
- Missing/not-connected and empty valuation states are distinguished.
- Holdings, observed history, as-of and provenance are server-backed.
- Investments and spending routes remain separate; focused spending-isolation/accuracy tests pass.
- /overview compatibility remains, and existing Accounts/Transactions/review navigation is retained in source.

## Verdict

**M3 verdict: NOT READY / FAIL.** Backend contracts and spending isolation pass, but the route does not yet expose the frozen scoped/date/coverage contract and the backend no-history fallback has a tax-scope leak. Keep INV-09 **in-progress** and INV-08 unchanged; implementation owner should address the findings, add regression coverage, and request re-verification.
