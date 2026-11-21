# Isolated investment ingestion — implementation handoff

## Implemented

- Plaid holdings adapter and bounded offset activity pagination; complete-response
  validation rejects unstable totals, duplicates and incomplete pages.
- Dedicated securities, holdings, activity, daily valuation and sync-state tables.
  New tables are created by existing `Base.metadata.create_all`; no bank-table
  migration or destructive backfill.
- Atomic per-Item synchronization with database-backed run acquisition, sanitized
  failure state, independent bank cursor, last-good retention and full-pull retry.
- Holdings reconciliation uses current flags. Activity corrections retain original
  payload plus revision count; removals are soft and restricted to the successfully
  read account/date window. Daily valuations retain original/latest provider
  account payloads and revision counts. Price timestamps stay in raw holdings.
- Missing balances remain null; unsupported currencies withhold totals. Account
  absence is explicitly missing coverage, not inferred closure. Observation times
  come from actual account valuations, not a later Item success that omitted it.
- Summary endpoint discloses value availability/coverage/freshness. Net worth adds
  investment account balances once, never holdings a second time, and exposes
  investment coverage. Unknown/mixed currency sums remain unsupported.
- Existing Item removal explicitly cleans account-scoped investment rows and
  sync state; shared security metadata can remain. No relink guessing by name/mask.
- Default-off `INVESTMENT_SYNC_ENABLED`; manual explicit date window only.
  No scheduler changes, Investments Refresh, real provider activation or live data.

## Migration / release / rollback

Before any live rollout, pass independent INV-05 review and INV-01 billing/provider
checks. Back up SQLite through its backup API and preserve host config. New tables
are additive; repeated create_all is tested. Keep `INVESTMENT_SYNC_ENABLED=false`
until the live gate is cleared. The existing consent gate is separate.

Do not downgrade to pre-INV-00 source after investment consent. If this ingestion
slice needs rollback, disable the sync flag and deploy the last spending-isolated
revision (`4d2e2f1`); keep new tables intact for recovery. Restoring a whole database
backup is not the normal rollback and can discard later bank/user changes.

A process killed after acquiring a run can leave status=running. Do not automatically
steal its lock: verify no worker is alive, then repair that Item's sync state in a
supervised operational action. Normal exceptions release it into error and retries
can proceed. No background retry loop or network error details in persisted errors.

## Boundaries / limitations

This is an implementer-verified development slice, not independent release approval.
No live investment endpoint has been called. Provider history/position completeness,
pricing, Fidelity/workplace coverage and real account-level currencies remain INV-01.
No tax overrides, flow reconciliation engine, return estimates, UI or allocation is
implemented here; existing confirmed funding evidence remains in the bank ledger.
Atomicity is per investment product pull; a bank sync is separate and remains usable
when investment sync fails. Foreign/malformed account ownership fails closed.

## Final implementer evidence

Source `f1fee3f`: full backend suite 394 passed, two pre-existing warnings.
Frozen red baseline at `11c1c61`: 20 expected failures; that test file remains
unchanged. Supplemental tests cover bank-failure independence, valuation
provenance, normalization/manual nickname preservation and provider endpoints.
No independent-verification or live deployment claim.
