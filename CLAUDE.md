# VibeLedger

Single-user personal finance ledger. FastAPI + SQLite + Plaid, with a multipage Streamlit dashboard (Accounts / Cashflow / Categories / Transfers) served alongside the API.

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
  main.py                    # FastAPI app, lifespan, middleware setup
  api/routes.py              # All API endpoints
  core/auth.py               # Bearer token middleware
  core/config.py             # Settings (from env vars)
  db/session.py              # SQLAlchemy engine + session
  db/schema_patches.py       # Idempotent ALTER TABLEs + backfills on startup (no migration framework)
  models/models.py           # ORM models (Item, Account, Transaction, TransferPair, AnnotationFingerprint, ...)
  schemas/plaid.py           # Pydantic request/response schemas
  services/
    connect_service.py       # Plaid Link session management
    plaid_client.py           # Plaid API wrapper (real + mock)
    security.py               # Fernet encrypt/decrypt for access tokens
    sync_service.py            # Transaction sync pipeline + annotation fingerprint reapply
    txn_fingerprint.py         # Content hash for transactions (account mask + date + amount + name)
    scheduler.py               # Background scheduled sync loop
    transfer_detector.py       # Heuristic pair-match for double-entry transfers
    refund_detector.py         # High-confidence refund matching + manual override support
Spend.py                     # Streamlit entry page and spending analysis
dashboard_lib.py             # Cached SQLite loaders + HTTP helpers for mutations
pages/
  0_Transfers.py             # Review queue: confirm/unpair, manual pairing
  1_Accounts.py              # Balances grouped by type, net worth estimate
  2_Cashflow.py              # Income, expenses, and net cashflow trend
  3_Cashflow_Sankey.py       # Income allocation into top-level category buckets
  4_Experimental.py          # Month-over-month movers and calendar heatmap
  5_Rules.py                 # Category rule management
  6_Transactions.py          # Transaction browsing and annotation
  7_Debt_and_Cash_Runway.py  # Placeholder for debt payoff and runway planning
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
- `GET /transactions` — supports `start_date`, `end_date`, `category`, `limit`, `offset`.
- `PATCH /transactions/{id}/annotation` — set `user_category`, `merchant_name_override`, `notes`, `reviewed`. Also upserts an `annotation_fingerprints` row keyed by the transaction's content hash, so the annotation survives item removal/re-link.
- `GET /annotations/fingerprints?unapplied_only=true` — list saved annotation fingerprints, optionally only those not currently matched to a live transaction.
- `POST /refunds/detect` — recompute automatic refund matches. Exact same-account, amount, and transaction-name matches become `likely`; Plaid refund codes become `confirmed`. Manual `confirmed`/`not_refund` choices override detection.

**Analytics:**
- `GET /analytics/monthly-spend`, `/category-spend`, `/cashflow-trend` — support `start_date`/`end_date`; exclude transfer-paired/`is_transfer_override` transactions by default (`?include_transfers=true` for raw numbers).
- `GET /analytics/accounts-summary` — balances by type + net worth.
- Confirmed/likely refunds reduce their expense category instead of being counted as income.

**Transfers (double-entry reconciliation):**
- `POST /transfers/detect` — pairs unpaired opposite-sign transactions on different accounts within `window_days` (default 3). Idempotent.
- `GET /transfers`, `POST /transfers` (manual pair), `POST /transfers/{id}/confirm`, `DELETE /transfers/{id}`.
- `is_transfer_override` on `transaction_annotations` flags transfers the heuristic can't pair (partial amounts, fees) — set via the Transfers dashboard page.

**Dashboard:**
- Reads SQLite directly (cached, fast); writes go through the FastAPI endpoints (auth/validation/transfer logic stay centralized).
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
