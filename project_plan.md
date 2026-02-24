# VibeLedger — Project Plan

## Overview
VibeLedger is a single-user personal finance app that aggregates transactions from multiple institutions via Plaid into a centralized local ledger, supports transaction annotations (category overrides + notes), and provides lightweight analytics dashboards.

## Basic Project Setup
- **Language:** Python
- **API framework:** FastAPI
- **Storage:** SQLite (source of truth)
- **ORM/migrations:** SQLAlchemy + Alembic
- **Testing:** pytest (minimal regression suite)
- **Scope posture:** single-user first, production-safe handling of Plaid tokens and transaction data

## MVP Boundary
- Connect accounts via Plaid Link (`link_token` + `public_token` exchange)
- Ingest data via `/transactions/sync` with cursor-based incremental updates
- Store canonical ledger in SQLite with idempotent upserts
- Support transaction annotations (user category, notes)
- Expose basic analytics-ready endpoints/queries:
  - monthly spend
  - category spend
  - income vs expenses trend

## Build Plan Overview
- **Phase 0:** bootstrap repo + app skeleton + DB schema + baseline tests
- **Phase 1:** Plaid integration endpoints + secure token handling primitives
- **Phase 2:** sync pipeline + cursor state + idempotent writes + tests
- **Phase 3:** transaction + annotation APIs + tests
- **Phase 4:** basic analytics endpoints + tests

## Execution Tracker

### Phase 0 — Bootstrap
- [x] Initialize local folder + git repo
- [x] Create Python project skeleton (FastAPI, modules, tests)
- [x] Add initial DB models and metadata
- [x] Add app bootstrap and health endpoint
- [x] Add baseline tests (health + model creation)

### Phase 1 — Plaid Integration
- [x] Add Plaid config plumbing (env-driven)
- [x] Implement `POST /plaid/link-token/create`
- [x] Implement `POST /plaid/public-token/exchange`
- [x] Persist Item + encrypted access token placeholder
- [x] Add tests for Plaid endpoint contracts (mocked)

### Phase 2 — Sync Pipeline
- [x] Implement transactions sync service wrapper (cursor-based)
- [x] Add idempotent upsert for added/modified/removed records
- [x] Persist sync cursor and sync run metadata
- [x] Add manual `POST /sync/item/{item_id}` trigger
- [x] Add tests for idempotency + mutation handling

### Phase 3 — Ledger + Annotations
- [x] Add `GET /transactions` with basic filters (date/account/category)
- [x] Add `PATCH /transactions/{id}/annotation`
- [x] Keep source fields immutable; annotation fields separate
- [x] Add tests for filtering + annotation update behavior

### Phase 4 — Analytics
- [x] Add `GET /analytics/monthly-spend`
- [x] Add `GET /analytics/category-spend`
- [x] Add `GET /analytics/cashflow-trend`
- [x] Add minimal tests for aggregation correctness
