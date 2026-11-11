# INV-01 — Investment coverage spike

Date: 2026-11-10. Baseline: `ec2a3ac`; roadmap: `86238d4`.
Status: **in progress; production coverage is not verified**.

## Implemented diagnostic

`PlaidClient.get_investment_readiness(access_token)` calls only `/item/get`
and `/accounts/get`, using an existing server-side token. It returns grouped
account types/subtypes and separate Investments flags for available, billed and
consented products. Missing fields are `null` (unknown), not false. No credentials,
account identifiers, names, masks or balances appear in its return value.

This is an internal adapter method, not a public route or operator CLI. Invoke
only through server-side code with the existing protected token-loading mechanism;
do not pass credentials on command lines. No production invocation has been made.
Mock output explicitly identifies itself and cannot establish real coverage.
Provider exceptions propagate; callers must not expose raw exceptions externally.

Even a positive product flag does **not** establish working holdings/activity,
plan entitlements, user consent for every account, pricing, or history. The method
always reports `coverage_verified: false`. No product-initializing investment
endpoint, Link creation, paid refresh, relink, or database write is performed.

## Coverage matrix

| Institution | Account class | Prior documentation research | Actual account test |
|---|---|---|---|
| Schwab | Taxable brokerage | General Investments access documented | Not tested |
| Schwab | Traditional IRA | Account-level verification required | Not tested |
| Schwab | Roth | Account-level verification required | Not tested |
| Schwab | Workplace | No inference from retail access | Not tested |
| Fidelity | Taxable brokerage | Access subject to plan/onboarding | Not tested |
| Fidelity | Traditional IRA | Account-level verification required | Not tested |
| Fidelity | Roth | Account-level verification required | Not tested |
| Fidelity | Workplace/NetBenefits | No inference from retail access | Not tested |

The documentation column summarizes the earlier research, not a fresh provider
check. Reference: https://plaid.com/docs/investments/ . Nothing in this matrix
asserts unsupported accounts or successful production access.

## Current code findings

- `PlaidClient.create_link_token` uses the global `plaid_products` setting,
  defaulting to `transactions`. It adds 730-day bank history options only for
  Transactions. That parameter is not investment-history configuration.
- There is no investment-specific Link path, update-mode path, holdings adapter,
  or investment activity ingestion. Do not globally add Investments yet: doing
  so can constrain ordinary bank linking and does not implement isolation.
- `SyncService.sync_item` refreshes accounts/snapshots and calls bank transaction
  sync inside the same savepoint. A transaction-sync failure rolls back the
  balances too. Investment-only Items need an independent sync operation.
- Shared account identity and `AccountBalanceSnapshot` can be reused, but current
  snapshots alone do not establish provider valuation timestamps or historical
  completeness. No historical daily values can be inferred from activity alone.
- Mixed-product Items require account-level routing. A depository cash-management
  account at an investment institution is not automatically an investment account.

## Link and ingestion requirements to carry into INV-02/04

1. Preserve the existing bank-link default. Introduce an explicit investment
   intent after the isolation contract/tests; request Investments only on that
   path. Do not require bank Transactions for an investment-only connection.
2. Examine existing Item availability/consent before deciding whether additional
   consent/update mode is required. Never remove/relink by default.
3. Keep holdings and investment activity separate from bank transactions. Do not
   invoke the bank sync pipeline for an investment-only Item.
4. Build server-side spending isolation before any production ingestion. Account
   balances contribute once to net worth; holdings are not additional wealth.
5. No UI navigation change is part of this coverage spike.

## Remaining evidence / release blockers

- Run the metadata diagnostic through authorized server-side access for relevant
  existing Items, retaining only a redacted summary. Missing linked accounts are
  a coverage gap, not evidence that their institution is unsupported.
- Verify dashboard Investments entitlement, Schwab/Fidelity OAuth access and
  contract billing; do not enable a paid product merely to complete the spike.
- After entitlement/consent are established, verify representative holdings and
  activity fields, account classes, price timestamps and actual oldest activity.
- Validate investment offset pagination, refresh/correction behavior and replay
  requirements against current provider documentation and actual permitted data.
  Bank `/transactions/sync` cursor semantics must not be assumed to apply.
- Record per-account currency support, missing basis/identifiers, missing prices,
  and retirement funds requiring manual allocation classification.

Minimum useful release remains independent investment sync plus observed balances,
holdings and dated snapshots, after INV-02–05. If provider access is delayed,
continue synthetic adapter/contract development without claiming production
coverage. An explicit statement-import workflow is a possible later fallback,
not implemented by this spike. INV-01 remains in progress; dependent tasks remain
unstarted until its acceptance criteria are satisfied.

## Local verification

- Red baseline: `python -m pytest tests/test_investment_readiness.py -q`:
  7 expected failures for the absent diagnostic method.
- Green: `python -m pytest tests/test_investment_readiness.py tests/test_plaid_client.py -q`:
  12 passed. Fake SDK transport only; no bank or ledger access.
- Checks cover endpoint allowlisting, no partial success on errors, mixed-account
  grouping, unknown metadata, mock provenance, and omission of sensitive fields.
- These are implementer-run checks, not independent verification or a release gate.

Full backend regression on source `2b1d2c2`: `python -m pytest -q` — 345 passed, 2 warnings. Roadmap scanner: 0 issues.
