# Spending isolation before Schwab consent

## Contract

Account type, never institution/name/subtype alone, defines the bank domain:
`depository`, `credit`, `loan`, and supported legacy `payment` wallets.
`investment`, legacy `brokerage`, unknown, and missing types are excluded from
bank reporting, activity, rule recomputation, category/merchant suggestions,
refund detection and new transfer matching. Include-transfers cannot bypass this.

Sync retains accounts/balance snapshots but skips investment transaction payloads
in both incremental and historical paths. Unknown transaction accounts fail the
batch atomically without advancing its cursor. Existing investment source records
are retained, not deleted, and filtered from the canonical SQL view and ORM
reporting boundary. No investment holdings/activity endpoint is called.

Previously confirmed funding pairs remain evidence and continue excluding bank
funding from household expenses. Unconfirmed cross-domain pairs cannot suppress
bank activity. New cross-domain pairing awaits the dedicated investment-flow
contract; unresolved bank funding remains visible. Existing automatic matches
remain subject to source-evidence revalidation. No institution-name heuristics.

## Validation

Initial red baseline: 3 failed (two ingestion cases and default Activity).
The dedicated suite now has 11 passing cases: mixed and historical ingestion,
legacy persistence/view filtering, include-transfers, five unknown/investment
classifications, parity across 11 API responses, and two atomic unknown-account
rollback cases. Existing cashflow oracles retain their original financial values.
Older synthetic bank-account fixtures explicitly declare depository type.
No independent human/agent review or live OAuth completion is claimed.

## Deployment and rollback

Inspect current units, env and route first; back up SQLite with its backup API.
Deploy exact committed source to the clean service checkout; restart API and
frontend; run deployment doctor and compare bank-only endpoint responses before
and after. Migration is additive consent-session columns plus rebuilt SQL view;
no source ledger deletion. Enable `INVESTMENT_LINK_ENABLED` only after checks.
Do not turn on scheduled sync, Investments Refresh, or holdings ingestion.

Rollback: disable investment linking and restart first. If consent has exposed
investment accounts, do not restore the old unisolated sync code with sync enabled.
Keep the isolated revision while repairing consent UI. Database backup is recovery
material, not an automatic restore that could discard subsequent ledger changes.
