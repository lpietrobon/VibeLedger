# VibeLedger

Single-user personal finance ledger. FastAPI + SQLite + Plaid, with a multipage Streamlit dashboard (Overview / Transactions / Spending / Cashflow / Accounts, plus Recurring / Flow / Transfers / Rules / Experimental / Add account under "More") served alongside the API.

## Setup

```bash
python3 -m venv .venv          # requires Python 3.11+
source .venv/bin/activate
pip install -e '.[dev,dashboard]'
```

- `dev` is enough for tests/API work; `dashboard` extra adds Streamlit/pandas/requests.
- If the venv breaks after moving the repo: `rm -rf .venv && python3 -m venv .venv && source .venv/bin/activate && pip install -e .[dev]`

## Running the app

**Do not run uvicorn/streamlit manually** (`nohup`+`&` won't survive agent exec boundaries). Two systemd **user** services do this, with lingering enabled so they survive reboot/logout:

| Service | Port | What | URL |
|---|---|---|---|
| `vibeledger.service` | 8000 | FastAPI (`--reload`, `--root-path /vibeledger`) | `/vibeledger/` |
| `vibeledger-dash.service` | 8501 | Streamlit dashboard | `/vibeledger/dash/` |

- **First action for agents:** `curl http://127.0.0.1:8000/health` and `curl http://127.0.0.1:8501/vibeledger/dash/_stcore/health` — both services are normally already up. Only restart on failure.
- Restart after code changes: `systemctl --user restart vibeledger` (app/.env) or `vibeledger-dash` (dashboard files).
- Logs: `journalctl --user -u vibeledger -n 100` (also `/tmp/vibeledger.log`); same pattern for `-dash`.
- **Never `pkill -f uvicorn/streamlit`** — use `systemctl --user restart <service>`.
- Edited a unit file? `systemctl --user daemon-reload` first.
- Requires `.env` (see `.env.example`); app refuses to start without `TOKEN_ENCRYPTION_KEY` (Fernet) and `VIBELEDGER_API_TOKEN`.

**Tailnet access** (already configured, persists across reboots — don't re-run unless routes are removed):
```bash
sudo tailscale serve --bg --set-path /vibeledger http://127.0.0.1:8000
sudo tailscale serve --bg --set-path /vibeledger/dash http://127.0.0.1:8501/vibeledger/dash
```
- `https://contabo.tail6fb821.ts.net/vibeledger/` → API, `.../vibeledger/dash/` → dashboard.
- The dashboard target URL repeats `/vibeledger/dash` because `--set-path` strips that prefix before proxying, and Streamlit's `--server.baseUrlPath` expects it back. The API doesn't need this trick (uvicorn `--root-path` accepts a stripped prefix).
- `.env`'s `APP_BASE_URL` must be exactly `https://contabo.tail6fb821.ts.net/vibeledger` (no trailing slash) — used to build Plaid Link `connect_url`.

**Troubleshooting:**
- `502 Bad Gateway` → nothing listening on `127.0.0.1:8000`; check `systemctl --user status vibeledger` / journal.
- `TOKEN_ENCRYPTION_KEY must be set` → `.env` not found by `EnvironmentFile=` in the unit.

### Linking a bank account

1. `POST /connect/sessions` (auth required) → returns `connect_url` + `session_token` (20min TTL).
2. Open `connect_url` in a browser, complete Plaid Link. Sandbox/non-OAuth institutions work over the tailnet alone.
3. OAuth institutions need `PLAID_REDIRECT_URI` reachable publicly — wrap with `sudo bash scripts/connect_funnel.sh open|close|status` (Tailscale Funnel for `/connect/*`).
4. Browser auto-posts to `/connect/complete` (unauthenticated by design) — access token is encrypted and stored.

**Transaction history:** new links request `days_requested=730` (Plaid's 2-year hard max; some institutions cap lower). Backfill is async (2–30 min) — re-run `/sync/item/{id}` if the first sync only returns ~90 days.

This setting is **not retroactive** for existing items. To extend history on an already-linked item:
1. `POST /items/{item_id}/remove` — removes the Plaid item and deletes local accounts/transactions/annotations/transfer pairs for it. Manual annotations are preserved via `annotation_fingerprints` (see below) and reapplied automatically on re-sync if the same transactions come back.
2. Re-link via the connect flow above.
3. `POST /sync/item/{new_item_id}` (retry after a few minutes for backfill).
4. `POST /category-rules/recompute-all` — categorization rules aren't applied automatically during sync.

## Test

```bash
pytest
```

Uses `PLAID_USE_MOCK=true` and a temp SQLite DB (`tests/conftest.py`). No external services needed. ~70 tests.

## Project layout

```
app/
  main.py                    # FastAPI app, lifespan, middleware, optional React frontend mount
  api/routes.py              # All API endpoints
  core/auth.py               # Bearer token middleware
  core/config.py             # Settings (from env vars)
  core/time.py               # utcnow() helper (timezone-aware UTC)
  db/base.py                 # SQLAlchemy declarative Base
  db/session.py              # SQLAlchemy engine + session
  db/schema_patches.py       # Idempotent ALTER TABLEs + backfills + effective_transactions view on startup (no migration framework)
  models/models.py           # ORM models (Item, Account, Transaction, TransactionAnnotation, AnnotationFingerprint,
                             #   CategoryRule, CategoryDecisionEvent, TransferPair, SyncState, SyncRun,
                             #   ConnectSession, AccountBalanceSnapshot, RecurringOverride)
  schemas/plaid.py           # Pydantic request/response schemas
  services/
    connect_service.py       # Plaid Link session management
    plaid_client.py          # Plaid API wrapper (real + mock)
    security.py              # Fernet encrypt/decrypt for access tokens
    sync_service.py          # Transaction sync pipeline + annotation fingerprint reapply
    txn_fingerprint.py       # Content hash for transactions (account mask + date + amount + name)
    scheduler.py             # Background scheduled sync loop
    transfer_detector.py     # Heuristic pair-match for double-entry transfers
    refund_detector.py       # High-confidence refund matching + manual override support
    recurring_detector.py    # Deterministic subscription / recurring-payment detection (pure functions)
    category_resolver.py     # Rule compilation + Plaid->friendly category map (shared by API and SQL view)
    category_catalog.py      # DEFAULT_CATEGORIES + merge of ledger/rule/default vocab for pickers (pure)
    search_query.py          # Canonical transaction search grammar (pure parser)
Spend.py                     # Streamlit "Overview" entry page (net worth, month spend/income, needs-attention)
dashboard_lib.py             # Cached SQLite loaders + HTTP helpers for mutations + shared nav/filters
pages/
  0_Transfers.py             # Review queue: confirm/unpair, manual pairing
  1_Accounts.py              # Balances grouped by type, net worth estimate
  2_Cashflow.py              # Income, expenses, and net cashflow trend
  2_Spending.py              # Spending analysis: category breakdown, comparison, drill-down
  3_Cashflow_Sankey.py       # Income allocation into top-level category buckets
  4_Experimental.py          # Month-over-month movers and calendar heatmap
  5_Rules.py                 # Category rule management
  6_Transactions.py          # Transaction browsing and annotation
  7_Debt_and_Cash_Runway.py  # Placeholder for debt payoff and runway planning
  8_Recurring.py             # Subscriptions & recurring payments review (reads /analytics/recurring)
  9_Add_Account.py           # Launch Plaid Link to connect a new bank account, then sync
analytics/                   # Standalone ad-hoc plotting scripts (not part of the dashboard app)
frontend/                    # Mobile-first React/Vite app (at parity with Streamlit for daily flows);
                             #   thin client — all analytics come from /analytics/* endpoints. See frontend/README.md.
scripts/
  connect_funnel.sh          # Tailscale Funnel automation for connect flow
  backup_db.sh               # SQLite backup (cron-friendly, 30-day retention)
tests/                       # pytest suite
```

## Common operations

All protected endpoints require `Authorization: Bearer <VIBELEDGER_API_TOKEN>`.

**Calling the API as an agent on this box:** read the token inline from `.env` per call — don't `export` it or ask the user for it:
```bash
curl -H "Authorization: Bearer $(grep ^VIBELEDGER_API_TOKEN .env | cut -d= -f2-)" \
  https://contabo.tail6fb821.ts.net/vibeledger/<endpoint>
```
The token gates tailnet access to Plaid-linked account data, so it stays.

**Sync:**
- `POST /sync/item/{item_id}` — sync one account; `POST /sync/all` — sync all.
- `SYNC_INTERVAL_HOURS` in `.env` enables automatic background sync (off by default).

**Transactions & annotations:**
- `GET /transactions` — supports `start_date`, `end_date`, `category`, `limit`, `offset`, and `q` (parsed search, see below).
- **Search grammar** (`app/services/search_query.py`, canonical + server-side): `q` accepts `merchant:`, `category:`/`cat:`, `account:`, `>50`/`<100` (absolute amount), `from:`/`to:` (YYYY-MM snaps to month bounds), `is:unreviewed|reviewed|uncategorized|refund|likely-refund|not-transfer|pending`, quoted values (`merchant:"blue bottle"`), and bare words as free text over name/merchant/category. A parent category matches its children (`FOOD` matches `FOOD/DINING`). Unknown `field:value` tokens fall through to free text rather than matching nothing. See `docs/transaction-search-spec.md`.
- `GET /transactions/search-suggestions?q=` — context-aware dropdown data: the field menu when between tokens, real DB values (ordered by frequency) inside a `field:` token. This is what makes the syntax discoverable instead of memorized.
- `GET /categories` — the vocabulary offered by category pickers: every category in use (with transaction counts), plus category-rule targets and a curated starter set (`DEFAULT_CATEGORIES` in `app/services/category_catalog.py`). Each item is `{value, count, source}` where source is `ledger|rule|default`. Case variants are merged — notably the SQL fallback literal `uncategorized` and a manual `UNCATEGORIZED` annotation collapse into one row. `PARENT/CHILD` is a convention, not an invariant: 1-level values (unmapped Plaid primaries) and 3+-level values are returned as-is.
- `PATCH /transactions/{id}/annotation` — set `user_category`, `merchant_name_override`, `notes`, `reviewed`. Also upserts an `annotation_fingerprints` row keyed by the transaction's content hash, so the annotation survives item removal/re-link.
- `GET /annotations/fingerprints?unapplied_only=true` — list saved annotation fingerprints, optionally only those not currently matched to a live transaction.
- `POST /refunds/detect` — recompute automatic refund matches. Exact same-account, amount, and transaction-name matches become `likely`; Plaid refund codes become `confirmed`. Manual `confirmed`/`not_refund` choices override detection.

**Analytics:**
- `GET /analytics/monthly-spend`, `/category-spend`, `/cashflow-trend` — support `start_date`/`end_date`; exclude transfer-paired/`is_transfer_override` transactions by default (`?include_transfers=true` for raw numbers).
- `GET /analytics/accounts-summary` — balances by type + net worth.
- `GET /analytics/recurring` — detected subscriptions/recurring payments grouped by merchant, with cadence (weekly/biweekly/monthly/quarterly/yearly), average amount, next expected date, monthly/annual estimates, and effective `status` (`active`/`inactive`) plus `auto_status` (what the detector inferred) and `manual_status` (`kept`/`canceled`/null). Supports `start_date`/`end_date`, `status`, `min_monthly`. Excludes transfers and refunds; detection logic is deterministic (`app/services/recurring_detector.py`).
- `POST /analytics/recurring/{merchant_key}/status` — manual status override, persisted per merchant in `recurring_overrides` (keyed by the detector's `merchant_key`): `kept` forces active, `canceled` forces inactive, `auto` clears it. The GET response's effective `status` and the active totals reflect the override, while `auto_status` preserves the detector's own call for auditing.
- `GET /analytics/overview` — one-shot Overview summary (net worth, current/previous month spend/income/net, needs-attention counts). Backs the React Overview screen.
- `GET /analytics/spending-summary?granularity=monthly|yearly` — period total, comparison, projection, top driver, and per-category diff.
- `GET /analytics/cumulative-spend?granularity=monthly|yearly` — cumulative spend pace for the current period vs the prior three.
- These three consolidate what the React client used to compute in the browser, so money math stays server-side (single source of truth). `GET /transactions` also accepts `q=` for server-side name/merchant/category search.
- Confirmed/likely refunds reduce their expense category instead of being counted as income.

**Transfers (double-entry reconciliation):**
- `POST /transfers/detect` — pairs unpaired opposite-sign transactions on different accounts within `window_days` (default 3). Idempotent.
- `GET /transfers`, `POST /transfers` (manual pair), `POST /transfers/{id}/confirm`, `DELETE /transfers/{id}`.
- A transfer is **only** a matched pair across two covered accounts — that is the sole thing that can double-count money as both income and expense. Analytics exclude paired transactions; nothing else.
- The legacy one-sided `is_transfer_override` column is **no longer honored**. It removed single transactions from every analytic with no counterparty, could not be set or cleared through any API (contrary to earlier docs), and survived re-sync via annotation fingerprints — so anything carrying it was silently and permanently missing from spend and income. The column remains for now but is inert.
- `POST /transfers/detect?reset_auto=true` discards unconfirmed auto pairs before re-detecting; confirmed and manual pairs are kept.

**Dashboard:**
- Reads SQLite directly (cached, fast); writes go through the FastAPI endpoints (auth/validation/transfer logic stay centralized). Server-computed analytics (e.g. the Recurring page) read via the API so the logic isn't duplicated in the dashboard.
- **Add account** (under "More") drives the connect flow from the browser: it calls `POST /connect/sessions` and opens the returned `connect_url` (Plaid Link), then offers `POST /sync/all`. Same flow as the curl steps in "Linking a bank account" below.
- Date range pickers default to the last 90 days even though more history may be loaded — widen the range to see older data.
- Restart after changes: `systemctl --user restart vibeledger-dash`.

## Key design decisions

- **Single-user, no accounts.** Auth is one bearer token (`VIBELEDGER_API_TOKEN`).
- **SQLite** at `~/.vibeledger/vibeledger.db`. No migration framework — schema auto-created via `create_all`, plus idempotent patches/backfills in `schema_patches.py`.
- **Plaid access tokens encrypted at rest** with Fernet (`TOKEN_ENCRYPTION_KEY`).
- **Tailscale-only networking.** App binds to localhost; never bind `0.0.0.0`.
- **Connect flow** uses short-lived sessions (20min TTL, 256-bit tokens) so `/connect/complete` can be unauthenticated.
- **Annotation fingerprints**: manual annotations are keyed by a content hash (account mask + date + amount + name) independent of `transaction_id`, so they survive transaction deletion/re-sync (e.g. item re-link).
- **Detailed Plaid category mapping**: `RENT_AND_UTILITIES_INTERNET_AND_CABLE` maps to `HOUSING/UTILITIES` before the broader primary-category fallback.
- **Overview counts must be reproducible by their drill-down.** Every `needs_attention` count is computed over transactions (never a bare count of annotation rows), and each Overview row links to a filter the Transactions screen turns into a server-side `q=` query (`FILTER_QUERY` in `frontend/src/routes/transactions.tsx`) — filtering a fetched page in the browser hides matches beyond it. Enforced by `tests/test_needs_attention_drilldown.py`.
- **Nothing cascades on delete.** No ORM relationships and SQLite FKs are off, so any code deleting a transaction must also drop its annotation, transfer pairs, and decision events (`SyncService._delete_dependent_rows`, `remove_item`); `schema_patches` purges orphans left by older builds. Orphaned rows are invisible to joins but still counted by aggregates, and SQLite rowid reuse can reattach them to unrelated transactions.
