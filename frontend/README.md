# VibeLedger Frontend (mobile app)

A mobile-first React/Vite consumer app for VibeLedger, at functional parity with
the Streamlit dashboard for the everyday flows. Streamlit is retained for the
desktop analyst views (Cashflow Sankey, Experimental movers/heatmap).

It started as a controlled import of the Lovable first draft from
`lpietrobon/vibeledger-vision` at commit `177a4fca110049b4777875d7683840770edf855e`,
and is intentionally a plain Vite React app, not the raw Lovable/TanStack Start scaffold.

## Architecture

- **All analytics are computed server-side.** The client only fetches finished
  numbers and renders them — no money math in the browser. Overview, spending
  summary, cumulative pace, and transaction search each map to one FastAPI
  endpoint (`/analytics/overview`, `/analytics/spending-summary`,
  `/analytics/cumulative-spend`, `/transactions?q=`). This keeps a single source
  of truth shared with Streamlit and keeps mobile payloads small.
- `src/lib/api/client.ts` is a thin fetch + snake→camel mapping layer.

## Run

```bash
npm install
npm run dev -- --port 5173
```

Open `http://127.0.0.1:5173/vibeledger/frontend/` when running locally.

The persistent local preview service is:

```bash
systemctl --user status vibeledger-frontend
```

Homepi is the canonical VibeLedger host. The preview service serves the built app on the homepi Tailscale IP:

```text
http://100.107.151.121:5173/vibeledger/frontend/
```

## Validate

```bash
npm run typecheck   # tsc --noEmit
npm run test        # vitest (client mapping contracts)
npm run build       # vite build
```

## Current State

- Uses real VibeLedger data through the same-origin `/vibeledger/api` proxy.
- Screens: **Overview, Spending, Transactions, Accounts**, plus under **More**:
  **Recurring** (subscriptions), **Category rules** (full create/edit/delete/apply),
  **Transfer detection** (detect/confirm/unpair), and **Add account** (Plaid Link).
- Write surface: annotation (single + batch), account nicknames, category-rule
  CRUD + apply, transfer confirm/unpair/detect, connect-session + sync.
- The frontend preview service builds the app, serves `/vibeledger/frontend/`, and
  proxies API calls to the local FastAPI service without exposing the bearer token
  to the browser.
