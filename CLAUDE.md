# VibeLedger

Single-user personal finance ledger. FastAPI + SQLite + Plaid.

## Setup

```bash
python3 -m venv .venv          # requires Python 3.11+
source .venv/bin/activate
pip install -e .[dev]
```

If the venv breaks after moving the repo (bad interpreter errors), recreate it: `rm -rf .venv && python3 -m venv .venv && source .venv/bin/activate && pip install -e .[dev]`

## Run

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --root-path /vibeledger
```

Requires a `.env` file (see `.env.example`). The app validates `TOKEN_ENCRYPTION_KEY` (Fernet) and `VIBELEDGER_API_TOKEN` at startup and refuses to start without them.

### Tailscale serve (already done, persists across reboots)

The Tailscale serve route has been configured once with sudo and persists permanently:

```bash
# Already run — do not re-run unless the route is removed
sudo tailscale serve --bg --set-path /vibeledger http://127.0.0.1:8000
```

This routes `https://contabo.tail6fb821.ts.net/vibeledger/` to the app (tailnet-only, not public internet). The route is stored by `tailscaled` and survives reboots. Other apps can be added the same way with their own prefix (e.g. `--set-path /app2`).

### Starting the app

```bash
cd /home/charlie/.openclaw/workspace/VibeLedger
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --root-path /vibeledger
```

Once running, the app is reachable at `https://contabo.tail6fb821.ts.net/vibeledger/` from any device on the tailnet. The `--root-path` flag is required so FastAPI generates correct URLs (connect flow links, docs, etc.).

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
  main.py              # FastAPI app, lifespan, middleware setup
  api/routes.py        # All API endpoints
  core/auth.py         # Bearer token middleware
  core/config.py       # Settings (from env vars)
  db/session.py        # SQLAlchemy engine + session
  models/models.py     # ORM models (Item, Account, Transaction, etc.)
  schemas/plaid.py     # Pydantic request/response schemas
  services/
    connect_service.py # Plaid Link session management
    plaid_client.py    # Plaid API wrapper (real + mock)
    security.py        # Fernet encrypt/decrypt for access tokens
    sync_service.py    # Transaction sync pipeline
    scheduler.py       # Background scheduled sync loop
scripts/
  connect_funnel.sh    # Tailscale Funnel automation for connect flow
  backup_db.sh         # SQLite backup (cron-friendly, 30-day retention)
tests/                 # pytest suite (34 tests)
analytics/             # Standalone Plotly/Streamlit scripts
```

## Common operations

All protected endpoints require `Authorization: Bearer <VIBELEDGER_API_TOKEN>`.

**Link a new bank account:**
1. `POST /connect/sessions` with `{"user_id": "..."}` — returns a `connect_url` and `session_token`
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
- `GET /analytics/monthly-spend`, `/analytics/category-spend`, `/analytics/cashflow-trend` — all support `start_date`/`end_date` filters

## Key design decisions

- **Single-user, no user accounts.** Auth is a single bearer token (`VIBELEDGER_API_TOKEN`).
- **SQLite.** DB at `~/.vibeledger/vibeledger.db`. No migration framework; schema auto-created on boot.
- **Plaid access tokens encrypted at rest** with Fernet (`TOKEN_ENCRYPTION_KEY`).
- **Tailscale for networking.** App binds to localhost; `tailscale serve --set-path /vibeledger` provides HTTPS on the tailnet. Never bind to `0.0.0.0`. Set `APP_BASE_URL=https://contabo.tail6fb821.ts.net/vibeledger` in `.env`.
- **Connect flow** uses short-lived sessions (20min TTL, 256-bit tokens) so `/connect/complete` can be unauthenticated (called from browser).
