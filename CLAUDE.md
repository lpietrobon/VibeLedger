# VibeLedger

Single-user personal finance ledger. FastAPI + SQLite + Plaid. Streamlit dashboard (multipage: Accounts / Cashflow / Categories / Transfers) served alongside the API.

## Setup

```bash
python3 -m venv .venv          # requires Python 3.11+
source .venv/bin/activate
pip install -e '.[dev,dashboard]'
```

The `dashboard` extra installs Streamlit/pandas/requests, needed only if you run or modify the dashboard. `dev` alone is enough to run tests or develop the API.

If the venv breaks after moving the repo (bad interpreter errors), recreate it: `rm -rf .venv && python3 -m venv .venv && source .venv/bin/activate && pip install -e .[dev]`

## Run

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --root-path /vibeledger
```

Requires a `.env` file (see `.env.example`). The app validates `TOKEN_ENCRYPTION_KEY` (Fernet) and `VIBELEDGER_API_TOKEN` at startup and refuses to start without them.

### Tailscale serve (already done, persists across reboots)

Two serve routes are configured permanently — both tailnet-only (not public internet), stored by `tailscaled`, survive reboots:

```bash
# Already run — do not re-run unless routes are removed
sudo tailscale serve --bg --set-path /vibeledger http://127.0.0.1:8000
sudo tailscale serve --bg --set-path /vibeledger/dash http://127.0.0.1:8501/vibeledger/dash
```

- `https://contabo.tail6fb821.ts.net/vibeledger/` → FastAPI on 127.0.0.1:8000
- `https://contabo.tail6fb821.ts.net/vibeledger/dash/` → Streamlit on 127.0.0.1:8501

**Why the dashboard target URL repeats `/vibeledger/dash`:** `--set-path` strips the matched prefix before proxying. Streamlit's `--server.baseUrlPath` expects the prefix to be present in both incoming requests and generated asset URLs. Putting `/vibeledger/dash` in the target URL makes the reverse proxy re-prepend what `--set-path` stripped, so Streamlit sees the full path it expects. The API avoids this hack because uvicorn's `--root-path /vibeledger` accepts a stripped prefix (ASGI root_path semantics).

Other apps can be added the same way with their own prefix (e.g. `--set-path /app2`).

### Starting the app

Two **systemd user services** run side-by-side (unit files at `~/.config/systemd/user/`). Lingering is enabled for user `charlie`, so both start at boot and survive logout. This is the **only supported way** to run them — do not launch uvicorn/streamlit manually with `nohup`+`&`, they won't survive agent exec boundaries (Claude-Code-style Bash tools reap their process group).

| Service | Port | What | URL |
|---|---|---|---|
| `vibeledger.service` | 8000 | FastAPI (uvicorn) | `/vibeledger/` |
| `vibeledger-dash.service` | 8501 | Streamlit dashboard | `/vibeledger/dash/` |

**For agents: both services are normally already running.** First actions should be `curl http://127.0.0.1:8000/health` and `curl http://127.0.0.1:8501/vibeledger/dash/_stcore/health`, not `systemctl start`. Only restart if a health check fails. **Never `pkill -f uvicorn` or `pkill -f streamlit`** — it leaves the managed process in a confused state; use `systemctl --user restart <service>` instead.

**Control the services:**
```bash
systemctl --user restart vibeledger          # API (after .env or app/ code change)
systemctl --user restart vibeledger-dash     # Dashboard (after dashboard_app.py / pages/ / dashboard_lib.py change)
systemctl --user status vibeledger vibeledger-dash
journalctl --user -u vibeledger -n 100       # API logs (also /tmp/vibeledger.log)
journalctl --user -u vibeledger-dash -n 100  # dash logs (also /tmp/vibeledger-dash.log)
```

Both unit files read `.env` via `EnvironmentFile=` and have `Restart=on-failure`. If you edit a unit file, run `systemctl --user daemon-reload` before restart.

Once running, the app is reachable at `https://contabo.tail6fb821.ts.net/vibeledger/` from any device on the tailnet. The `--root-path /vibeledger` flag (baked into the unit's `ExecStart`) is required so FastAPI generates correct URLs (connect flow links, docs, etc.).

**Verify it's up:**
```bash
systemctl --user is-active vibeledger vibeledger-dash                        # both "active"
curl -sS http://127.0.0.1:8000/health                                        # API local
curl -sS http://127.0.0.1:8501/vibeledger/dash/_stcore/health                # dash local
curl -sS https://contabo.tail6fb821.ts.net/vibeledger/health                 # API tailnet
curl -sS https://contabo.tail6fb821.ts.net/vibeledger/dash/_stcore/health    # dash tailnet
```

**Troubleshooting:**
- `502 Bad Gateway` from `contabo.tail6fb821.ts.net/vibeledger/...` — tailscale serve is proxying correctly but nothing is listening on `127.0.0.1:8000`. Run `systemctl --user status vibeledger` and `journalctl --user -u vibeledger -n 50` to see why it's down.
- Startup failure `TOKEN_ENCRYPTION_KEY must be set...` — means `EnvironmentFile=` isn't finding `.env`. Verify the path in the unit file and that `.env` exists and is readable.
- Tailscale serve config (persistent): `tailscale serve status` should show `/vibeledger proxy http://127.0.0.1:8000` under `https://contabo.tail6fb821.ts.net`.
- `.env`'s `APP_BASE_URL` must be exactly `https://contabo.tail6fb821.ts.net/vibeledger` — no trailing slash, no duplicated `/vibeledger`. This is the base used to build `connect_url` returned by `POST /connect/sessions`. After changing, `systemctl --user restart vibeledger`.

### Linking a new bank account

The Plaid Link widget runs entirely in the browser. The `/connect/complete` callback is a `fetch` from the browser (not from Plaid's servers), so the app only needs to be reachable by the browser — tailnet access is sufficient for sandbox and non-OAuth institutions.

The funnel script is only needed if using OAuth-based institutions (which redirect through `PLAID_REDIRECT_URI`). For those cases:

```bash
sudo bash scripts/connect_funnel.sh open     # expose /vibeledger/connect via Tailscale Funnel
# complete the Plaid Link flow in browser
sudo bash scripts/connect_funnel.sh close    # remove public exposure when done
```

`status` shows current funnel state: `sudo bash scripts/connect_funnel.sh status`

## Test

```bash
pytest
```

Tests use `PLAID_USE_MOCK=true` and an in-memory SQLite DB (configured in `tests/conftest.py`). No external services needed.

## Project layout

```
app/
  main.py                    # FastAPI app, lifespan, middleware setup
  api/routes.py              # All API endpoints (incl. /transfers, /analytics/accounts-summary)
  core/auth.py               # Bearer token middleware
  core/config.py             # Settings (from env vars)
  db/session.py              # SQLAlchemy engine + session
  db/schema_patches.py       # Idempotent ALTER TABLEs on startup (no migration framework)
  models/models.py           # ORM models (Item, Account, Transaction, TransferPair, ...)
  schemas/plaid.py           # Pydantic request/response schemas
  services/
    connect_service.py       # Plaid Link session management
    plaid_client.py          # Plaid API wrapper (real + mock)
    security.py              # Fernet encrypt/decrypt for access tokens
    sync_service.py          # Transaction sync pipeline
    scheduler.py             # Background scheduled sync loop
    transfer_detector.py     # Heuristic pair-match for double-entry transfers
dashboard_app.py             # Streamlit entry page (overview + shared filters)
dashboard_lib.py             # Cached SQLite loaders + HTTP helpers for mutations
pages/
  1_Accounts.py              # Balances grouped by type, net worth estimate
  2_Cashflow.py              # Monthly income vs expense, net trend
  3_Categories.py            # Top categories, MoM, samples
  4_Transfers.py             # Review queue: confirm/unpair, manual pairing
scripts/
  connect_funnel.sh          # Tailscale Funnel automation for connect flow
  backup_db.sh               # SQLite backup (cron-friendly, 30-day retention)
tests/                       # pytest suite (47 tests)
analytics/                   # Standalone Plotly/Streamlit scripts (legacy)
```

## Common operations

All protected endpoints require `Authorization: Bearer <VIBELEDGER_API_TOKEN>`.

### Calling the API from an agent on this box

Agents running on this VPS (e.g. openclaw/Claude Code instances) should read the token inline from `.env` on every call. Do **not** `export` it into a shell session, and do **not** ask the user to paste it — it's already on disk and the agent has filesystem access.

Canonical pattern:

```bash
curl -H "Authorization: Bearer $(grep ^VIBELEDGER_API_TOKEN /home/charlie/.openclaw/workspace/VibeLedger/.env | cut -d= -f2-)" \
  https://contabo.tail6fb821.ts.net/vibeledger/<endpoint>
```

Rationale: keeps the token out of the agent's conversation context and environment while still letting the agent make calls autonomously. The token is a single-user bearer used to gate access from other devices on the tailnet; removing it would expose Plaid-linked account data to anyone on the tailnet, so it stays.

**Link a new bank account:**
1. `POST /connect/sessions` with `{"user_id": "..."}` — **requires `Authorization: Bearer $VIBELEDGER_API_TOKEN`** (only `/connect/start` and `/connect/complete` are exempt from auth, so the browser hop works unauthenticated). Returns a `connect_url` and `session_token`. Example:
   ```bash
   curl -X POST https://contabo.tail6fb821.ts.net/vibeledger/connect/sessions \
     -H "Authorization: Bearer $VIBELEDGER_API_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"user_id": "you"}'
   ```
   Missing/wrong token returns `{"detail":"invalid or missing bearer token"}` (401).
2. Open `connect_url` in a browser to complete Plaid Link (if the app isn't publicly reachable, temporarily expose `/connect/*` via Tailscale Funnel)
3. On success the browser posts back to `/connect/complete` automatically — the access token is encrypted and stored

**Sync transactions:**
- `POST /sync/item/{item_id}` — sync a single linked account
- `POST /sync/all` — sync all active accounts
- Set `SYNC_INTERVAL_HOURS` in `.env` to enable automatic background sync (disabled by default)

**Query transactions:**
- `GET /transactions` — list transactions. Supports query params: `start_date`, `end_date`, `category`, `limit`, `offset`
- `PATCH /transactions/{id}/annotation` — add user category, notes, or mark reviewed

**Analytics:**
- `GET /analytics/monthly-spend`, `/analytics/category-spend`, `/analytics/cashflow-trend` — all support `start_date`/`end_date`. By default they exclude transactions that are part of a `TransferPair` or flagged `is_transfer_override=true` (so credit-card payments don't double-count). Pass `?include_transfers=true` for raw numbers.
- `GET /analytics/accounts-summary` — current balances grouped by type, plus assets / liabilities / net-worth estimate.

**Transfers (double-entry reconciliation):**
- `POST /transfers/detect` — heuristic: pair any unpaired outflow (`amount > 0`) with an unpaired opposite-sign match on a *different* account within `window_days` (default 3). Idempotent.
- `GET /transfers` — list pairs with both sides expanded.
- `POST /transfers` — manual pair (`{"txn_a_id", "txn_b_id"}`). Rejects same-account, amount-mismatch, or already-paired txns.
- `POST /transfers/{id}/confirm` — mark an auto-detected pair as confirmed.
- `DELETE /transfers/{id}` — unpair.
- `PATCH /transactions/{id}/annotation` can also set `is_transfer_override` via Python (no schema field exposed in `PatchAnnotationRequest` yet — set directly via the dashboard's Transfers page or SQL if needed).

### Dashboard notes

- Multipage Streamlit lives in [dashboard_app.py](dashboard_app.py) + [pages/](pages/). [dashboard_lib.py](dashboard_lib.py) is the shared loader (cached direct SQLite reads) and the thin wrapper for API mutations (auth header loaded inline from `.env`).
- The dashboard reads SQLite directly for read paths (fast, no token plumbing) and calls the FastAPI endpoints for writes (so auth middleware, validation, and transfer logic stay centralized).
- `is_transfer_override` on [transaction_annotations](app/models/models.py) is a lightweight flag for transfers the heuristic can't pair (e.g. partial amounts, fee deductions). Set via the Transfers page.
- To bring the dashboard up after a code change: `systemctl --user restart vibeledger-dash`.

## Key design decisions

- **Single-user, no user accounts.** Auth is a single bearer token (`VIBELEDGER_API_TOKEN`).
- **SQLite.** DB at `~/.vibeledger/vibeledger.db`. No migration framework; schema auto-created on boot.
- **Plaid access tokens encrypted at rest** with Fernet (`TOKEN_ENCRYPTION_KEY`).
- **Tailscale for networking.** App binds to localhost; `tailscale serve --set-path /vibeledger` provides HTTPS on the tailnet. Never bind to `0.0.0.0`. Set `APP_BASE_URL=https://contabo.tail6fb821.ts.net/vibeledger` in `.env`.
- **Connect flow** uses short-lived sessions (20min TTL, 256-bit tokens) so `/connect/complete` can be unauthenticated (called from browser).
