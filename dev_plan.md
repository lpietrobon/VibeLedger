# VibeLedger Consolidated Dashboard

## Context

Today `dashboard_app.py` is a single-page Streamlit app focused on category spend. It reads SQLite directly and has no notion of multiple accounts as a first-class view or of transfers (e.g. a credit-card payment leaves checking as a negative and lands on the credit card as a positive — today that double-counts in cashflow).

Goal: grow this into a Mint/Monarch-style consolidated view. First cut covers three tabs — **Accounts Summary**, **Cashflow**, **Categories** — plus transfer reconciliation that both views depend on. Net-worth trend is deferred (only 3 balance snapshots exist, needs a separate backfill story).

## Approach

Extend the existing Streamlit app to a multi-page layout, add a lightweight transfer-pair table with heuristic matching + a manual override UI, and teach cashflow/category views to exclude transfers.

### 1. Schema additions

Add one table via `Base.metadata.create_all()` (no migrations — matches project convention in [CLAUDE.md](../../.openclaw/workspace/VibeLedger/CLAUDE.md)):

- `transfer_pairs(id, txn_out_id FK, txn_in_id FK, detected_by TEXT['auto'|'manual'], confirmed BOOL, created_at)` — UNIQUE on each txn id so a transaction belongs to at most one pair.

Also add one column on `transaction_annotations`:
- `is_transfer_override BOOL` — lets the user force-flag a single side as a transfer even without a matched pair (edge case: intra-day or fee-adjusted pairs the heuristic misses).

Define in [app/models/models.py](../../.openclaw/workspace/VibeLedger/app/models/models.py). Tables are auto-created on boot per [app/main.py](../../.openclaw/workspace/VibeLedger/app/main.py) lifespan.

### 2. Transfer detection service

New module `app/services/transfer_detector.py`:

- `detect_candidates(session, window_days=3)` — for each unpaired transaction with `amount > 0`, find an unpaired transaction on a *different account* with `amount == -this.amount` and `abs(date - other.date) <= window_days`. Prefer nearest date, then same Plaid category if available.
- Insert auto-matched rows with `detected_by='auto', confirmed=False`.
- Idempotent: skip txns already in a pair.
- Run on demand (endpoint + Streamlit button) — not on every sync, keeps sync hot path untouched.

Hook a thin endpoint `POST /transfers/detect` into [app/api/routes.py](../../.openclaw/workspace/VibeLedger/app/api/routes.py) so the dashboard can trigger it. Add `GET /transfers` (list with pagination) and `DELETE /transfers/{id}` (unpair) so the manual-override UI has real endpoints rather than raw SQL from Streamlit.

### 3. Cashflow correction

Update `/analytics/cashflow-trend` and `/analytics/monthly-spend` in [app/api/routes.py](../../.openclaw/workspace/VibeLedger/app/api/routes.py) to `LEFT JOIN transfer_pairs` and exclude any transaction whose id appears on either side of a pair, plus any txn whose annotation has `is_transfer_override=true`. Add a query param `include_transfers=false` (default) so the old behavior is still reachable.

Category-spend should exclude the *outflow* side (credit-card payments shouldn't show as a "Payment" category spike) but is otherwise unaffected.

### 4. Streamlit multi-page dashboard

Restructure [dashboard_app.py](../../.openclaw/workspace/VibeLedger/dashboard_app.py) into Streamlit's native multipage layout:

```
dashboard_app.py              # entry, sidebar filters (date range, accounts), shared loader
pages/
  1_Accounts.py               # balances grouped by type; assets vs liabilities totals
  2_Cashflow.py               # monthly income/expense/net bars; transfer-excluded
  3_Categories.py             # port current category explorer
  4_Transfers.py              # review queue: auto-matched pairs awaiting confirm, unpair, manual pair
```

Extract the `load_df` helper into a shared `dashboard_lib.py` (alongside `dashboard_app.py`) with a cached (`@st.cache_data(ttl=60)`) loader plus a transfer-aware view that returns `(transactions_df, transfer_pairs_df)`.

**Accounts page**: query `accounts` directly, group by `type` (depository/credit). Assets = sum of depository `current_balance`. Liabilities = sum of credit `current_balance` (Plaid reports positive = owed). Show a table per group and a headline `Net = assets - liabilities`.

**Cashflow page**: monthly bars (income = sum of negative amounts * -1, expense = sum of positive amounts, net = income - expense) with transfers excluded via the corrected endpoint or inline SQL. Show same period MoM delta.

**Categories page**: keep current logic from [dashboard_app.py:61-86](../../.openclaw/workspace/VibeLedger/dashboard_app.py#L61-L86), but source from the transfer-excluded frame.

**Transfers page**: table of pairs with columns [date_out, date_in, amount, account_out, account_in, detected_by, confirmed]. Buttons: Confirm, Unpair. A second section lets the user pick two transactions and manually pair them (calls `POST /transfers` with two txn ids). A third section shows `is_transfer_override` toggles for lonely transfers.

### 5. How the dashboard reaches the API

Keep direct SQLite reads for the heavy frames (fast, no token plumbing in Streamlit). For *mutations* (confirm/unpair/detect), call the FastAPI endpoints with the bearer token loaded inline from `.env` using the canonical pattern in [CLAUDE.md](../../.openclaw/workspace/VibeLedger/CLAUDE.md#L120-L127). This keeps the write path auditable and reuses existing auth middleware.

## Files to modify / create

- Modify: [app/models/models.py](../../.openclaw/workspace/VibeLedger/app/models/models.py) — add `TransferPair`, extend `TransactionAnnotation`
- Create: `app/services/transfer_detector.py`
- Modify: [app/api/routes.py](../../.openclaw/workspace/VibeLedger/app/api/routes.py) — add `/transfers/*`, update `/analytics/*`
- Modify: [dashboard_app.py](../../.openclaw/workspace/VibeLedger/dashboard_app.py) — becomes entry page + shared filters
- Create: `dashboard_lib.py`, `pages/1_Accounts.py`, `pages/2_Cashflow.py`, `pages/3_Categories.py`, `pages/4_Transfers.py`
- Create: `tests/test_transfer_detector.py` — seed a known pair, assert it matches; seed a pair with 4-day gap, assert it does not; assert idempotency.

## Reuse

- Existing signed-amount convention in [dashboard_app.py:53](../../.openclaw/workspace/VibeLedger/dashboard_app.py#L53) (`amount > 0` = spend) carries through.
- `effective_category` COALESCE from [dashboard_app.py:17](../../.openclaw/workspace/VibeLedger/dashboard_app.py#L17) stays as the canonical category expression.
- `analytics/` standalone scripts already compute balance-by-type and timelines — port their SQL into `dashboard_lib.py` rather than rewriting.

## Verification

1. `pytest` — new transfer detector tests pass; existing analytics tests still pass (may need updating for the `include_transfers` default change).
2. Seed data: pick a known credit-card payment in `vibeledger.db` that currently double-counts; run `POST /transfers/detect`; confirm the pair appears and the affected month's cashflow drops by that amount.
3. `streamlit run dashboard_app.py` locally; walk each of the four pages with real DB data. Check Accounts page totals match `SELECT type, SUM(current_balance) FROM accounts GROUP BY type`.
4. Confirm the systemd-managed API still responds: `curl http://127.0.0.1:8000/health` after `systemctl --user restart vibeledger`.

## Deferred (not in this plan)

- Net-worth trend line — needs a daily balance-snapshot backfill job first; today only 3 snapshots exist for 8 accounts.
- Replacing Streamlit with a FastAPI-served SPA.
- Smarter transfer heuristics (partial-amount matches, multi-leg paydowns).
