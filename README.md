# VibeLedger

Single-user personal finance ledger with Plaid ingestion.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
uvicorn app.main:app --reload
pytest
```

## Required environment variables

```bash
PLAID_CLIENT_ID=...
PLAID_SECRET=...
PLAID_ENV=sandbox   # switch to production for real accounts
PLAID_PRODUCTS=transactions
PLAID_COUNTRY_CODES=US
PLAID_REDIRECT_URI=
PLAID_USE_MOCK=false
APP_BASE_URL=https://<your-public-url>
TOKEN_ENCRYPTION_KEY=<fernet-key>
CONNECT_SIGNING_KEY=<different-random-secret>
```

- `TOKEN_ENCRYPTION_KEY`: encrypts/decrypts stored Plaid `access_token` values in DB (Fernet key).
- `CONNECT_SIGNING_KEY`: signs temporary connect session tokens in URL callbacks.
- `PLAID_USE_MOCK=false`: enables real Plaid API calls (set `true` only for local mock mode).

Generate a Fernet key:

```bash
python - <<'PY'
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
```

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
