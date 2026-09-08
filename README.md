# VibeLedger

Single-user personal finance ledger with Plaid ingestion and a React/Vite product UI. A Mint/Monarch-style consolidated view with double-entry transfer reconciliation, category rules, refund matching, and subscription detection.

## Prerequisites

- Python **3.11+** (required by `pyproject.toml`)
- Plaid developer credentials (Sandbox or Production)
- Optional: `tailscale` if you want automated connect tunnel open/close

## Quick start

```bash
python3 -m venv .venv          # requires Python 3.11+
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload
```

In a separate shell, run tests:

```bash
source .venv/bin/activate
pytest
```

### Fixing a broken venv

Venvs embed absolute paths in their script shebangs. If you move the project directory, rename your user, or clone onto a different machine, the venv will break with "bad interpreter" errors. Recreate it:

```bash
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Required environment variables

```bash
PLAID_CLIENT_ID=...
PLAID_SECRET=...
PLAID_ENV=sandbox          # switch to production for real accounts
PLAID_PRODUCTS=transactions
PLAID_COUNTRY_CODES=US
PLAID_REDIRECT_URI=
PLAID_USE_MOCK=false
APP_BASE_URL=https://<your-public-url>
TOKEN_ENCRYPTION_KEY=<fernet-key>
```

- `TOKEN_ENCRYPTION_KEY`: encrypts/decrypts stored Plaid `access_token` values in DB (Fernet key). Validated at startup.
- `PLAID_USE_MOCK=false`: enables real Plaid API calls. Set `true` only for local development without Plaid credentials.

Generate a Fernet key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Optional connect tunnel automation

If you expose `/connect/start` through a short-lived tunnel (for example via Tailscale Funnel), you can let the app open/close it during the connect flow:

```bash
CONNECT_TUNNEL_AUTOMATION=1
CONNECT_TUNNEL_STRICT=1
```

The tunnel script is hard-coded to `scripts/connect_funnel.sh` relative to the project root.

- With `CONNECT_TUNNEL_STRICT=1`, tunnel script failures return API errors.
- With `CONNECT_TUNNEL_STRICT=0`, failures are logged and the flow continues.

## How connect + token storage works

1. You trigger account linking (from Discord -> backend creates connect session).
2. Backend returns a short-lived URL: `/connect/start?session=...`.
3. If needed, you temporarily expose the backend URL (e.g., Tailscale Funnel), then open it on phone/laptop.
4. Browser runs Plaid Link and returns a `public_token`.
5. Browser posts `public_token + session_token` to backend `/connect/complete`.
6. Backend exchanges `public_token -> access_token` server-to-server with Plaid.
7. Backend encrypts `access_token` with `TOKEN_ENCRYPTION_KEY` and stores ciphertext in SQLite.
8. You close the temporary public tunnel.
9. Scheduled sync jobs decrypt token in memory, call Plaid `/transactions/sync`, and update ledger.

No Funnel is required for recurring sync jobs; only outbound backend->Plaid access is needed.

## Database

The default database path is `~/.vibeledger/vibeledger.db`. Override with `DATABASE_URL` env var. The directory is created automatically at startup.

Tables are auto-created via `Base.metadata.create_all()` on boot. There is no migration framework, but `app/db/schema_patches.py` runs on startup after `create_all` to apply idempotent `ALTER TABLE`s, backfills, and to (re)create the `effective_transactions` SQL view — so column additions to existing tables are handled automatically without a drop. Back up `~/.vibeledger/vibeledger.db` before larger changes.

## Product UI

The React/Vite app in `frontend/` provides the consolidated view:

- **Overview** — net worth, current-month spend/income vs last month, and a "needs attention" queue.
- **Transactions** — browse, filter (power-user query syntax), and annotate (category/merchant/notes/reviewed/refund).
- **Spending** — category breakdown, period comparison, and drill-down.
- **Cashflow** — monthly income vs expense and net trend (transfers excluded by default).
- **Accounts** — balances grouped by type with assets/liabilities/net-worth; per-account nicknames.
- **Recurring** — detected subscriptions/recurring payments with cadence, next expected charge, and monthly/annual cost estimates.
- **Transfers** — auto-detected pairs (e.g. credit-card payments crossing checking + credit) awaiting confirmation, plus manual pairing and `is_transfer_override` toggles. Transfer-paired transactions are excluded from cashflow/spend analytics so they don't double-count.
- **Rules** — manage regex/amount-based category rules with preview and apply.
- **Add account** (under "More") — launch Plaid Link in the browser to connect a new bank, then sync.

Run locally:

```bash
npm install && npm run dev -- --port 5173
```

See `frontend/README.md` for the preview service and validation commands.

## Production deployment

### Tailscale HTTPS (recommended)

Use `tailscale serve` to proxy the app with automatic HTTPS:

```bash
# Start the app on localhost
uvicorn app.main:app --host 127.0.0.1 --port 8000

# In another shell, expose via Tailscale with HTTPS
tailscale serve --bg https / http://127.0.0.1:8000
```

The app is now reachable at `https://<your-machine>.tail1234.ts.net` with a valid TLS certificate, accessible only from your Tailnet.

**Bind to Tailscale IP only (alternative):**

```bash
uvicorn app.main:app --host $(tailscale ip -4) --port 8000
```

### Running as a systemd service (optional)

If you want the app to start on boot and restart on failure, create a systemd unit:

```ini
# /etc/systemd/system/vibeledger.service
[Unit]
Description=VibeLedger
After=network-online.target tailscaled.service
Wants=network-online.target

[Service]
Type=simple
User=<your-user>
WorkingDirectory=/path/to/VibeLedger
EnvironmentFile=/path/to/VibeLedger/.env
ExecStart=/path/to/VibeLedger/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now vibeledger
```

### Recommended env vars for production

```bash
VIBELEDGER_API_TOKEN=<strong-random-token>
ALLOWED_HOSTS=<your-machine>.tail1234.ts.net
SYNC_INTERVAL_HOURS=0
APP_BASE_URL=https://<your-machine>.tail1234.ts.net
```

## Notes

- **Single-threaded SQLite.** Concurrent API requests are serialized at the DB level. Fine for single-user.
- **No migration framework.** Column additions and backfills are applied idempotently on startup by `app/db/schema_patches.py`; only larger structural changes may warrant a manual rebuild. Back up `~/.vibeledger/vibeledger.db` before changes.
- **Link token expiry.** Plaid link tokens expire after 4 hours. The 20-minute session TTL mitigates this in practice.
