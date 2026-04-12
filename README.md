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
CONNECT_SIGNING_KEY=<different-random-secret>
```

- `TOKEN_ENCRYPTION_KEY`: encrypts/decrypts stored Plaid `access_token` values in DB (Fernet key).
- `CONNECT_SIGNING_KEY`: signs temporary connect session tokens in URL callbacks.
- `PLAID_USE_MOCK=false`: enables real Plaid API calls (`true` is local mock mode only).

Generate secure keys:

```bash
python - <<'PY'
import secrets
from cryptography.fernet import Fernet

print("TOKEN_ENCRYPTION_KEY=", Fernet.generate_key().decode())
print("CONNECT_SIGNING_KEY=", secrets.token_urlsafe(32))
PY
```

## Optional connect tunnel automation

If you expose `/connect/start` through a short-lived tunnel (for example via Tailscale Funnel), you can let the app open/close it during the connect flow:

```bash
CONNECT_TUNNEL_AUTOMATION=1
CONNECT_TUNNEL_STRICT=1
CONNECT_TUNNEL_SCRIPT=./scripts/connect_funnel.sh
CONNECT_TUNNEL_CWD=/absolute/path/to/repo
```

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

## Known issues and fixes

This section tracks implementation defects identified during review. Ordered roughly by impact.

### Correctness bugs

#### 1. `/analytics/monthly-spend` reports net flow, not spend
`app/api/routes.py` — `monthly_spend` sums every transaction amount, so refunds and Plaid-negative income rows cancel out real spending. It also takes no date filter and scans all history on every call.

**Fix:** sum only positive amounts (Plaid's outflow convention) and accept `start_date` / `end_date` query params. Optionally exclude `pending=true`.

```python
db.query(
    func.strftime("%Y-%m", Transaction.date).label("month"),
    func.sum(case((Transaction.amount > 0, Transaction.amount), else_=0)),
).group_by("month")
```

#### 2. `/analytics/cashflow-trend` is mathematically wrong
`app/api/routes.py` — the query aggregates `SUM(amount)` per month first, then branches on the sign of the *already-aggregated* total to populate `income` vs `expenses`. A month with $5k income and $4k spend nets $1k positive and gets reported as `expenses=1000, income=0`.

**Fix:** split positive and negative amounts at the row level before summing, with two conditional aggregates:

```python
db.query(
    func.strftime("%Y-%m", Transaction.date).label("month"),
    func.sum(case((Transaction.amount > 0, Transaction.amount), else_=0)).label("expenses"),
    func.sum(case((Transaction.amount < 0, -Transaction.amount), else_=0)).label("income"),
).group_by("month")
```
Then compute `net = income - expenses` in Python.

#### 3. `/analytics/category-spend` silently drops unannotated transactions
`app/api/routes.py` — inner-joins `TransactionAnnotation`, so any transaction without an annotation row is excluded from the result. The Streamlit dashboard already uses the correct "effective category" semantics and the two will disagree.

**Fix:** LEFT OUTER JOIN and `COALESCE(annotation.user_category, transaction.plaid_category_primary, 'uncategorized')` as the grouping key. Also restrict to positive amounts if you want spend rather than net.

#### 4. Sync `_apply_changes` is not idempotent
`app/services/sync_service.py` — two bugs in the same function:
- In the `added` loop, if the txn already exists it's booked as `modified_count += 1`. The separate `modified` loop then runs over its own list and can double-count the same row on replay.
- The `raw_json` column is filled from the already-normalized dict, not the actual Plaid payload, so you've lost the original fields you'd want for debugging.

**Fix:**
- Make "added-but-exists" a no-op (log and continue), and only the `modified` loop should increment `modified_count`.
- Pass the raw Plaid dict through `sync_transactions` alongside the normalized form and store that in `raw_json`. Or rename the column to `normalized_json` and be honest about what it holds.

#### 5. Concurrent `/sync/item/{id}` calls race
`app/services/sync_service.py` — two simultaneous sync calls both read the same cursor, both call Plaid, and both commit. You'll get duplicate `SyncRun` rows and potentially apply the same batch twice.

**Fix:** before starting, check for an in-progress `SyncRun` for the item and return 409, or acquire a row-level lock on `SyncState` with `with_for_update()` (requires switching off SQLite or accepting that SQLite serializes writes anyway — document the assumption).

#### 6. `AccountBalanceSnapshot` has no uniqueness, piles up duplicates
`app/services/sync_service.py` — every sync appends a new snapshot row with `as_of_date=today`. Hourly syncs → 24 rows per account per day.

**Fix:** add a unique constraint on `(account_id, as_of_date)` and upsert (update the existing row if present, otherwise insert).

#### 7. `GET /transactions?category=` filter is annotation-only
`app/api/routes.py` — filters only on `TransactionAnnotation.user_category`. A category that matches `plaid_category_primary` on unannotated rows returns nothing, and the result disagrees with the dashboard's effective-category view.

**Fix:** filter on `COALESCE(annotation.user_category, transaction.plaid_category_primary) == category`, matching the dashboard semantics.

### Security / design

#### 8. Signed session token + DB lookup is security theater
`app/services/connect_service.py` — the session token is HMAC-signed *and* the full signed string is stored in the database and looked up on every request. The HMAC adds zero value: any attacker who can present a token that exists in the DB has already won; any attacker who can't fails the DB lookup regardless of signature.

**Fix:** pick one model and commit to it.
- **Simpler:** drop the HMAC, use `secrets.token_urlsafe(32)` as a pure random token, validate by DB lookup. Delete `CONNECT_SIGNING_KEY`.
- **Stateless:** drop the DB row, use a signed JWT-style token carrying `user_id` and `exp`. Requires adding a replay guard (nonce or one-shot flag).

#### 9. `/plaid/link-token/create` and `/plaid/public-token/exchange` are unauthenticated
`app/api/routes.py` — the Connect-session flow exists specifically to guard account linking, but these two endpoints bypass it entirely. Anyone reachable on the host (including anyone on the temporary Funnel path) can mint a link token or exchange a public token.

**Fix:** remove these two routes and make Connect sessions the only path to linking. If you need them for local debugging, gate them behind a `127.0.0.1`-only dependency or a `DEBUG_MODE` env flag.

#### 10. `CONNECT_TUNNEL_SCRIPT` is env-controlled and executed
`app/api/routes.py` — `_run_connect_tunnel` reads a script path from env on every session creation and executes it via `subprocess.run`. Not shell-injectable (no `shell=True`), but a foot-gun.

**Fix:** hard-code the script path (or a whitelist) in code. Keep only `CONNECT_TUNNEL_AUTOMATION=1` as the on/off toggle.

#### 11. Every `/connect/start` GET mints a new Plaid link_token
`app/api/routes.py` — a browser refresh burns a Plaid API call.

**Fix:** add a `link_token` column to `ConnectSession`, mint it once on `create_session`, and reuse it until the session expires or completes.

### Plumbing / hygiene

#### 12. Alembic claimed, not used
`project_plan.md` lists "SQLAlchemy + Alembic" but `app/main.py` calls `Base.metadata.create_all()` at startup and there is no `alembic/` directory.

**Fix:** for a single-user SQLite app, `create_all` is fine — drop the Alembic claim from the plan. If you want real migrations, `alembic init alembic` and wire it up.

#### 13. Deprecated `datetime.utcnow()`
`datetime.utcnow()` is used throughout `app/models/models.py`, `app/services/`, `app/api/routes.py`, and `tests/test_connect_service.py`. Deprecated in Python 3.12 and returns naive datetimes that mix badly with any tz-aware comparison.

**Fix:** replace with `datetime.now(timezone.utc)` everywhere and store tz-aware `DateTime(timezone=True)` columns. (The FastAPI `on_event("startup")` variant of this issue has already been migrated to a `lifespan` context manager in `app/main.py` — no action needed there.)

#### 14. Test coverage still has gaps
Recent commits added `tests/test_sync_service.py`, `tests/test_connect_service.py`, and `tests/test_transaction_routes.py`, which is a real improvement — sync state tracking, connect token tampering, and annotation + date-range filtering are now exercised. What's still missing:
- **Sync replay idempotency (the #4 bug above).** `test_sync_service` covers a clean added→modified→removed sequence but never sends the same txn in the `added` list twice. Add a test that replays the same `added` batch and asserts `added_count` stays stable and `modified_count` does not spuriously increment.
- **Analytics correctness.** None of the three `/analytics/*` endpoints have a test. Seed a ledger with known positive/negative amounts across two months and assert exact numbers — this test is what will catch the bugs in #1, #2, #3 when you fix them.
- **Category filter against `plaid_category_primary`.** `test_transaction_routes` only tests category filtering on an annotated row, so the #7 bug (unannotated-but-Plaid-categorized rows dropped by the filter) is not covered.

#### 15. `vibeledger.db` in the working tree
A 430 KB SQLite file sits next to the code. `.gitignore` excludes `*.db`, but the file is still on disk and will be included in any tarball/copy.

**Fix:** move the default DB to an app-data dir outside the repo, e.g. `database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{Path.home()}/.vibeledger/vibeledger.db")`, and create the dir on startup.

#### 16. `PLAID_USE_MOCK` defaults to `true` but README says `false`
`app/core/config.py` — a fresh deploy that forgets to set the env var runs silently in mock mode and looks like it's working.

**Fix:** default to `false` in code and require an explicit opt-in for mock mode. Tests already set their own env.

#### 17. `validate_security_settings` uses a weak Fernet key check
`app/core/config.py` — `len(key) < 32` is a proxy; Fernet keys are 44-char base64-encoded 32-byte secrets, and a random 32-char string will pass length-check but fail at decrypt time.

**Fix:** call `Fernet(key.encode())` inside a try/except at startup and fail fast on any exception.

#### 18. `list_transactions` hard-caps at 500 with no pagination
`app/api/routes.py` — any client that needs history silently gets truncated.

**Fix:** add `limit` and `offset` query params with sensible bounds, and return a `total` count alongside the rows.

#### 19. `Numeric` columns silently become floats
`app/models/models.py` — amounts are declared `Numeric(12, 2)` (good) but typed as `float` in the Mapped hints, and analytics code immediately casts to `float`. You lose the decimal precision the moment you do arithmetic.

**Fix:** type the hints as `Decimal` and keep values as `Decimal` until JSON serialization. Serialize with `str(decimal_value)` to avoid FP coercion on the wire.

### Quick-fix priority order
1. Analytics bugs (#1, #2, #3) — these produce wrong numbers today.
2. Sync idempotency + concurrency (#4, #5, #6) — silent data corruption on replay.
3. Unauthenticated Plaid endpoints (#9) — one-line routing fix.
4. Connect session token model (#8) — decide and simplify.
5. Test coverage (#14) — unblocks safe refactoring of everything above.
