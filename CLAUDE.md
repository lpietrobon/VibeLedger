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

The app runs as a **systemd user service** (`vibeledger.service` at `~/.config/systemd/user/vibeledger.service`). Lingering is enabled for user `charlie`, so the service starts at boot and survives logout. This is the **only supported way** to run the app in this environment — do not launch uvicorn manually with `nohup`+`&`, it won't survive agent exec boundaries (Claude-Code-style Bash tools reap their process group).

**For agents: the service is normally already running.** Your first action should be `curl http://127.0.0.1:8000/health`, not `systemctl start`. Only restart if the health check fails. **Never run `pkill -f uvicorn`** — it kills the systemd-managed process and leaves the service in a confused state; use `systemctl --user restart vibeledger` instead.

**Control the service:**
```bash
systemctl --user start vibeledger        # start
systemctl --user stop vibeledger         # stop
systemctl --user restart vibeledger      # restart (after .env or code change)
systemctl --user status vibeledger       # status
journalctl --user -u vibeledger -n 100   # recent logs (also mirrored to /tmp/vibeledger.log)
```

The unit file reads `.env` via `EnvironmentFile=`, runs `/home/charlie/.openclaw/workspace/VibeLedger/.venv/bin/uvicorn`, and has `Restart=on-failure`. If you edit the unit file, run `systemctl --user daemon-reload` before restart.

Once running, the app is reachable at `https://contabo.tail6fb821.ts.net/vibeledger/` from any device on the tailnet. The `--root-path /vibeledger` flag (baked into the unit's `ExecStart`) is required so FastAPI generates correct URLs (connect flow links, docs, etc.).

**Verify it's up:**
```bash
systemctl --user is-active vibeledger                          # should print "active"
curl -sS http://127.0.0.1:8000/health                          # local
curl -sS https://contabo.tail6fb821.ts.net/vibeledger/health   # through tailscale
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
- `GET /analytics/monthly-spend`, `/analytics/category-spend`, `/analytics/cashflow-trend` — all support `start_date`/`end_date` filters

## Key design decisions

- **Single-user, no user accounts.** Auth is a single bearer token (`VIBELEDGER_API_TOKEN`).
- **SQLite.** DB at `~/.vibeledger/vibeledger.db`. No migration framework; schema auto-created on boot.
- **Plaid access tokens encrypted at rest** with Fernet (`TOKEN_ENCRYPTION_KEY`).
- **Tailscale for networking.** App binds to localhost; `tailscale serve --set-path /vibeledger` provides HTTPS on the tailnet. Never bind to `0.0.0.0`. Set `APP_BASE_URL=https://contabo.tail6fb821.ts.net/vibeledger` in `.env`.
- **Connect flow** uses short-lived sessions (20min TTL, 256-bit tokens) so `/connect/complete` can be unauthenticated (called from browser).
