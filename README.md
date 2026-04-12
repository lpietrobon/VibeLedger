# VibeLedger

Single-user personal finance ledger with Plaid ingestion.

## Prerequisites

- Python **3.11+** (required by `pyproject.toml`)
- Plaid developer credentials (Sandbox or Production)
- Optional: `tailscale` if you want automated connect tunnel open/close

## Quick start

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
uvicorn app.main:app --reload
```

In a separate shell, run tests:

```bash
source .venv/bin/activate
pytest
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

Tables are auto-created via `Base.metadata.create_all()` on boot. There is no migration framework; for schema changes on an existing DB, drop and recreate (acceptable for single-user use).

## Readiness assessment

### Sensitive data exposure

- **Git history is clean.** No `.db` files, `.env` files, real API keys, or financial data have ever been committed. The `.gitignore` correctly excludes `*.db`, `*.sqlite3`, `.env`, and virtualenvs.
- `.env.example` contains empty placeholder values only.
- Access tokens are encrypted at rest via Fernet; the encryption key is never stored in the repo.

### Sandbox mode

Ready. With `PLAID_USE_MOCK=true`, the app runs entirely against mock data with no external calls. With valid sandbox credentials (`PLAID_CLIENT_ID`, `PLAID_SECRET`, `PLAID_ENV=sandbox`), the connect flow and transaction sync work against Plaid's sandbox environment end-to-end.

To test sandbox mode:

1. Set `PLAID_USE_MOCK=false`, `PLAID_ENV=sandbox`, and provide sandbox credentials.
2. Generate a `TOKEN_ENCRYPTION_KEY` (see above).
3. Start the server and create a connect session via `POST /connect/sessions`.
4. Open the connect URL, link a sandbox institution, and trigger sync via `POST /sync/item/{id}`.

### Production mode

Not yet ready. The following should be addressed before pointing at real financial accounts:

- **No authentication on the API.** All endpoints are open to anyone who can reach the host. Before production use, add at minimum a bearer token check or restrict to localhost/VPN.
- **No HTTPS enforcement.** The app itself serves plain HTTP; it relies on a reverse proxy or tunnel for TLS. Ensure this is in place before handling real credentials.
- **No error recovery in sync.** If a sync call to Plaid fails mid-way, the `SyncRun` stays in `running` status and blocks future syncs until manually cleaned up. Add try/except around the Plaid call with proper status update on failure.
- **No scheduled sync.** Transaction ingestion is manual (`POST /sync/item/{id}`). For production use, add a cron or background scheduler to sync periodically.
- **Single-threaded SQLite.** Concurrent API requests are serialized at the DB level. Fine for single-user, but monitor for lock contention if adding automation.
- **Link token expiry.** Plaid link tokens expire after 4 hours. The cached `link_token` on `ConnectSession` is not refreshed — if a session lingers, the link token may expire before the user opens it. The 20-minute session TTL mitigates this in practice.
