# Investment ingestion contract — 2026-11-15

## Scope and gate

Schwab-first, provider-independent fixture development. INV-01 remains the live
coverage/billing gate, not a prerequisite for synthetic tests. No live investment
data calls, automatic refresh, or paid activation in this slice. Fidelity and
workplace coverage remain unknown. Bank sync and investment sync are independent.

## Storage and API

Reuse encrypted Item and Account identities. Separate investment securities,
current holdings, activity, daily observed valuations and per-Item sync state.
Security identity is provider security_id, never ticker alone. Securities retain
provider metadata (type, identifiers, currency); unsupported/missing fields stay
null. Holdings are keyed by account/security; replay updates, never duplicates.
Activity is keyed by provider investment_transaction_id, not content hashes.
Changes retain a revision count and original raw provenance. Full successful
window reads soft-remove absent activity in that window only. Partial reads never
remove anything. Corrections restore a removed row if its ID returns. Account
identity conflicts across Items fail atomically.

A successful pull commits holdings, bounded activity, security metadata, account
balances, daily observed values and success state together. Failed/partial pulls
retain last-good rows/success time and record a sanitized error type. State is
independent from bank SyncState. A concurrent run is rejected. No bank sync or
Transactions endpoint is called from investment sync. Missing account types fail
closed; only investment/brokerage are ingested. Mixed Items preserve checking.

Dedicated POST /investments/sync/{item_id} is default-disabled behind
INVESTMENT_SYNC_ENABLED. Date window is explicit, inclusive, at most 730 days.
GET /investments/summary exposes account valuation availability, currency,
last-success/as-of and freshness, not invented returns. No UI in this slice.
Holdings/activity use dedicated tables and cannot enter Transaction.

## Provider contract

Holdings: /investments/holdings/get. Activity: /investments/transactions/get,
explicit start/end, count=500 and offset pagination. Read all pages before writes.
Reject changing total counts, repeated transaction IDs, empty premature pages,
account/security identity conflicts, malformed values and out-of-window activity.
Retry is a whole idempotent pull after failure; no blind retry of billed refresh.
No Investments Refresh endpoint. Offset pagination is not a Transactions cursor.
Provider history depth is not historical valuation coverage.

## Consumers and classification

INV-00's canonical account boundary covers posted_activity/reporting_scope,
Activity/search/suggestions/categories, recurring, monthly/category/daily/cumulative
spending, Overview review counts, cashflow/Sankey/timeline and SQL exports via
effective_transactions. Rule preview/apply and refund/transfer detection obey the
same bank boundary. Legacy investment rows remain stored but excluded even with
include_transfers=true. Raw maintenance queries are not spending exports.
Bank types: depository, credit, loan, payment. Investment cash and cash management
reported as investment stay investment; depository cash-management stays bank.
Unknown types are excluded pending review, never classified by institution name.

## Literal event boundaries (USD)

| Event | Investment evidence | Bank/spending treatment |
|---|---|---|
| Checking funds brokerage 200 | External deposit 200 | Bank row retained; excluded only with confirmed reconciliation |
| Brokerage withdraws 100 | External withdrawal 100 | Bank receipt retained; unresolved status not silently hidden |
| Schwab transfers 300 to Fidelity | Account withdrawal/deposit 300 | Pooled external flow 0 once both legs reconciled |
| Buy fund 80 / sell 90 | Trade, not contributed capital | No spending/income row |
| Dividend 5 reinvested | Investment income 5 and buy 5 | No paycheck or household expense |
| Fee 2 | Investment expense, reduces gain | Not household spending |
| Cash sweep 50 | Internal movement | No contribution or expense |
| In-kind transfer supported value 400 | External flow 400 at boundary | Unknown value blocks returns; never cash assumed |
| Retirement rollover 500 | Transfer, not tax-year contribution | Pooled flow 0 if both selected |
| Bank payment named Schwab 75, unknown counterparty | Unresolved | Remains inspectable and counted; no name exclusion |

Opening 1000 + deposit 200 + gain 50 = ending 1250. Opening 1000 - withdrawal
100 + gain 50 = ending 950. These are future flow/return contracts, not metrics
implemented by this ingestion slice. No tax contribution inference or tax advice.

## Values, corrections and lifecycle

Account balance is counted once in consolidated net worth; never add holdings on
top. Missing balance is null, not zero. Investment summary withholds total if any
included account is missing value or has non-USD/unknown currency, while showing
per-account coverage. Stale (>24h) or failed latest attempt is disclosed. Daily
values begin at first successful observation; no invented pre-link price history.
Store observed_at separately from provider price/as-of fields in raw holdings.
No tax-treatment guessing beyond raw provider subtype; corrections/overrides are
reserved for later UX and must remain separate from provider-owned fields.

Absent accounts are not inferred closed. Their last-good rows are retained and
coverage explicitly marked missing; current holdings for present accounts are
reconciled on full success. Item removal removes its investment rows and sync
state with its accounts; global security catalog may remain. Relink uses new
provider IDs without speculative matching/deduplication by mask/name. No duplicate
net-worth claim across separately linked real-world accounts. Preserve the
existing duplicate-account coverage warning. Manual bank annotations remain
untouched. Cross-domain evidence requires future explicit linkage, not copying
investment activity into the spending ledger.
