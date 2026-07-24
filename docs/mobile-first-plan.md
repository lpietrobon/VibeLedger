# Mobile-first frontend plan

Goal: make the React/Vite app (`frontend/`) the primary, phone-first VibeLedger
UI, reaching functional parity with the Streamlit dashboard while eliminating the
duplicated business logic that currently lives in the browser.

Status: **Phases 1–3 landed** (backend consolidation endpoints, client refactored
onto them, and parity screens: Rules CRUD, Transfers actions, Recurring, Add
account). Remaining: Phase 4 (PWA polish) and Phase 5 (cutover). Streamlit is
still canonical and retained. This is a living plan — revise as we go.

## Principles

1. **One source of truth.** All money math (spend, income, net worth, projections,
   category rollups, recurring, refund netting, transfer exclusion) is computed
   **once, server-side**, and the client only renders. The `effective_transactions`
   SQL view + `/analytics/*` endpoints are canonical. The recurring feature
   (`recurring_detector.py` → `GET /analytics/recurring` → thin UI) is the model.
2. **Thin client, small payloads.** A phone screen fetches a ~1 KB summary, not
   500 raw transactions. No business rules re-encoded in TypeScript.
3. **Parity before cutover.** Streamlit stays canonical and running until React
   covers the full write surface. No feature is "done" until it can read *and*
   write what Streamlit can.
4. **Mobile-first, not mobile-only.** Layouts target a phone viewport first;
   desktop is a widened version of the same components.

## Current state (baseline)

- React routes: Overview, Spending, Transactions, Accounts, More, Rules (read-only),
  Transfers (read-only). No Recurring, no Add-account.
- React write surface: annotation, batch annotation, account nickname, sync-all.
- **Client-side analytics to remove** (in `frontend/src/lib/api/client.ts`):
  - `getOverviewSummary` — 4 fetches + JS KPI/needs-attention math.
  - `getCumulativeSpending` — pulls 4 months of raw transactions, sums per day.
  - `getSpendingSummary` — projections, %change, top driver in JS.
  - `getCategoryComparison` — diffs two months of category-spend in JS.
  - `getTransactions(query)` — client-side text filter within a single 500-row page.
- Serving: `frontend/preview-server.mjs` serves built `dist/` and reverse-proxies
  `/vibeledger/api/*` to FastAPI, **injecting the bearer token server-side** so the
  browser never holds it. Not built or mounted by default (no `dist/`).
- All write-surface endpoints for parity **already exist** (category-rules CRUD +
  preview/apply, transfers detect/confirm/pair/delete, connect sessions, sync,
  recurring). Only the analytics-consolidation endpoints below are new.

## Phase 0 — Decisions to lock first

- **Serving/auth model.** Keep the token-injecting reverse proxy (`preview-server.mjs`)
  as a systemd user service (`vibeledger-frontend`), served over the tailnet at
  `/vibeledger/frontend/`. This reuses the existing bearer-token model with zero
  auth rework. (Alternative for later: a cookie-session login so FastAPI can serve
  `dist/` directly via its existing `/frontend` mount — deferred; not needed for a
  single-user tailnet.)
- **Canonical URL.** During transition: React at `/vibeledger/frontend/`, Streamlit
  stays at `/vibeledger/dash/`. Flip the default only after Phase 3.
- **Testing bar for frontend.** `npm run build` + `npx tsc --noEmit` must pass in CI/
  pre-commit; add a minimal Vitest smoke test for the API client mappers. Backend
  endpoints get pytest coverage as usual.

## Phase 1 — Backend data contract (eliminate client-side analytics)

New thin FastAPI endpoints that return finished numbers. Each ships with pytest
contract tests and reuses existing helpers (`_effective_*_expr`,
`_apply_transfer_exclusion`, `overview`/`spending` logic ported from
`dashboard_lib.py` into a shared service so Streamlit and the API agree).

1. `GET /analytics/overview`
   → `{ as_of_date, net_worth, assets, liabilities, month_spend, prev_month_spend,
   month_income, prev_month_income, net_cashflow, prev_net_cashflow,
   needs_attention: { unreviewed, uncategorized, likely_refunds, transfer_pairs_pending } }`
   Replaces `getOverviewSummary` (4 fetches → 1).
2. `GET /analytics/spending-summary?granularity=monthly|yearly`
   → `{ period_label, total, previous_total, change, change_pct, projection,
   top_driver, category_comparison: [{category, current, previous}] }`
   Replaces `getSpendingSummary` + `getCategoryComparison`.
3. `GET /analytics/cumulative-spend?granularity=monthly|yearly`
   → `[{ x, current, previous1, previous2, previous3 }]` (day-of-period cumulative).
   Replaces `getCumulativeSpending`. Reuses `cumulative_series`/`period_bounds_n`.
4. `GET /transactions?q=` — server-side text/merchant/category filter over the full
   set (not one page). Extends the existing endpoint; keep pagination correct.

**Definition of done:** every screen's numbers come from one endpoint; no analytics
math remains in `client.ts`; Streamlit and API return identical figures for the
same inputs (add a cross-check test).

## Phase 2 — React client refactor (no visual change)

- Rewrite `client.ts` to call the Phase 1 endpoints and delete the compute helpers.
- Delete dead `mock-data.ts` fixtures (keep only `CATEGORY_COLORS`, or move colors
  to a small `theme.ts`).
- Wire React Query cache keys to the new endpoints; add proper loading/error states.
- Keep the existing Overview/Spending/Transactions/Accounts screens pixel-identical;
  this phase is purely swapping the data source.

**Definition of done:** all four existing data screens render from backend summaries;
`tsc --noEmit` + `build` green; payloads verified small (no 500-row fetches for KPIs).

## Phase 3 — Parity features (write surface + missing screens)

Backend already exists for all of these; work is React screens + wiring.

- **Rules** (`/rules`): create / edit / enable-disable / delete, plus preview
  (`/category-rules/preview`) and apply (`/category-rules/apply`). Mobile: list +
  edit sheet, dry-run preview count before apply.
- **Transfers** (`/transfers`): detect, confirm, unpair, manual-pair, and
  `is_transfer_override` toggle. Mobile: review queue with swipe/confirm actions.
- **Recurring** (new `/recurring` route): render `GET /analytics/recurring` — cadence,
  next expected, monthly/annual estimates, active/inactive filter, variable-amount flag.
- **Add account** (new route under More): `POST /connect/sessions` → open `connect_url`
  (Plaid Link) in a new tab → poll `/connect/sessions/{token}` → `POST /sync/all`.
  Mirrors the Streamlit `9_Add_Account.py` page.

**Definition of done:** React can do everything Streamlit can except the intentionally
desktop-only analyst views (Sankey/Flow, Experimental movers/heatmap — see Phase 5).

## Phase 4 — Mobile-first polish

- **PWA**: web manifest + service worker (installable to home screen, offline app
  shell, cached last-known summaries). Icons, theme color, safe-area insets.
- **IA & touch**: bottom-tab nav (already present) tuned to 5 primary destinations;
  ≥44px touch targets; sticky headers; pull-to-refresh triggers sync.
- **Feel**: skeleton loaders, optimistic annotation updates with rollback, toast on
  save, empty states.
- **Perf budget**: initial JS < ~200 KB gzipped; each screen ≤ 1 network round-trip
  for its primary data.

**Definition of done:** installs as a PWA on iOS/Android home screen; primary flows
usable one-handed; Lighthouse mobile PWA + performance pass.

## Phase 5 — Cutover & deprecation

- Promote React to the default `/vibeledger/` experience; keep Streamlit at
  `/vibeledger/dash/` as the "advanced/desktop" surface for the analyst-only views
  (Sankey, Experimental) that aren't ported.
- Update `CLAUDE.md` / `README.md` to describe React as the primary UI and Streamlit
  as the desktop/advanced companion.
- Add/adjust systemd services (`vibeledger-frontend`) and tailnet serve paths; document
  build/deploy (`npm run build` in the unit's `ExecStartPre` or a deploy script).
- Decide per-page whether to retire the now-duplicated Streamlit pages or keep them.

## Testing strategy

- **Backend**: pytest contract tests for each Phase 1 endpoint; a parity test asserting
  API numbers match the ported shared analytics functions.
- **Frontend**: `tsc --noEmit` + `vite build` gate every change; Vitest unit tests for
  `client.ts` response mappers; optional Playwright smoke test for the four core screens
  against a mock-served API.
- **No bloat**: one meaningful test per behavior; delete fixtures/tests that duplicate
  coverage.

## Risks / open questions

- **Auth for direct FastAPI-served SPA.** Deferring cookie-session; relying on the Node
  proxy. Revisit if we want to drop the extra service.
- **Analytics parity.** Porting `dashboard_lib` math into a shared service must not
  change existing Streamlit outputs — lock with cross-check tests before deleting TS.
- **Scope of "parity".** Confirm Sankey/Flow and Experimental stay desktop-only rather
  than getting mobile screens (they're dense analyst views).
- **Plaid Link on mobile.** OAuth institutions still need `PLAID_REDIRECT_URI` publicly
  reachable (funnel); confirm the mobile connect flow handles the redirect return.

## Suggested sequencing (first shippable increments)

1. Phase 1 endpoints `/analytics/overview` + `/transactions?q=` (+ tests).
2. Phase 2 refactor of Overview & Transactions screens onto them — **first shippable
   mobile win**, no drift.
3. Phase 1 spending-summary + cumulative-spend; Phase 2 Spending screen.
4. Phase 3 Recurring + Add-account (high user value, backend already done).
5. Phase 3 Rules + Transfers write flows.
6. Phase 4 PWA polish → Phase 5 cutover.
