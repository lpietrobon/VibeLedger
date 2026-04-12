# VibeLedger

Single-user personal finance ledger. FastAPI + SQLite + Plaid.

## Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Run

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Requires a `.env` file (see `.env.example`). The app validates `TOKEN_ENCRYPTION_KEY` (Fernet) and `VIBELEDGER_API_TOKEN` at startup and refuses to start without them.

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
tests/                 # pytest suite (34 tests)
analytics/             # Standalone Plotly/Streamlit scripts
```

## Key design decisions

- **Single-user, no user accounts.** Auth is a single bearer token (`VIBELEDGER_API_TOKEN`).
- **SQLite.** DB at `~/.vibeledger/vibeledger.db`. No migration framework; schema auto-created on boot.
- **Plaid access tokens encrypted at rest** with Fernet (`TOKEN_ENCRYPTION_KEY`).
- **Tailscale for networking.** App binds to localhost; `tailscale serve` provides HTTPS. Never bind to `0.0.0.0`.
- **Connect flow** uses short-lived sessions (20min TTL, 256-bit tokens) so `/connect/complete` can be unauthenticated (called from browser).
