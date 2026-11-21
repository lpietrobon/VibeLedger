# VibeLedger Frontend (mobile app)

A mobile-first React/Vite consumer app for VibeLedger. It is the product UI for
daily flows and analytics, including cashflow and inspectability surfaces.

It started as a controlled import of the Lovable first draft from
`lpietrobon/vibeledger-vision` at commit `177a4fca110049b4777875d7683840770edf855e`,
and is intentionally a plain Vite React app, not the raw Lovable/TanStack Start scaffold.

## Architecture

- **All analytics are computed server-side.** The client only fetches finished
  numbers and renders them — no money math in the browser. Overview, spending
  summary, cumulative pace, and transaction search each map to one FastAPI
  endpoint (`/analytics/overview`, `/analytics/spending-summary`,
  `/analytics/cumulative-spend`, `/transactions?q=`). This keeps a single source
  of truth and keeps mobile payloads small.
- `src/lib/api/client.ts` is a thin fetch + snake→camel mapping layer.
- **Installable PWA.** `vite-plugin-pwa` generates a web app manifest + service
  worker (Workbox), so the app installs to a phone home screen or a laptop desktop
  and opens full-screen. The service worker precaches the app shell and keeps a
  last-known copy of `/analytics/*` responses (NetworkFirst), so it opens instead
  of a blank page when offline. Icons live in `public/` (`pwa-*.png`,
  `maskable-512x512.png`, `apple-touch-icon-180x180.png`, `favicon.svg`).

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

GitHub Actions is the authoritative validation environment for these gates. The
`Tests / frontend` job runs all three checks on every push and pull request and
retains the production `dist/` artifact for seven days. Homepi deployment smoke
checks confirm that an already-validated build starts and renders; they do not
replace CI when local memory pressure prevents a clean frontend toolchain run.

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

## Shared reporting dates

Use `DateRangeSelection` and `rangeQuery` from `src/lib/dateRange.ts` for
inclusive date-only request bounds. An explicit `comparison` rule controls KPI
comparison independently of the preset and historical pace overlays. `none`
omits comparison bounds. `initialDateSelection` defaults to None; pages may
explicitly choose an initial rule. `defaultComparison` is a compatibility name
for the selected rule, not an inferred preset default. `presetComparison` remains
available for callers intentionally choosing an initial default only.

`DateRangeSelector` preserves the comparison when presets or custom dates change,
except All-time clears it. Native From/To fields keep invalid intermediate edits
local, without emitting a new request selection. `allowComparison={false}` hides
the rule for Activity; `allowAll` enables unbounded Activity dates. It labels
literal bounds and unequal mapped durations. Backend reporting metadata, not the
selector, owns coverage qualification. URL persistence and page-level parity are
tracked separately by TIME-04/05.

Run date tests with `TZ=America/Los_Angeles npm test` for the explicit local-clock
fixtures; pure date arithmetic uses UTC calendar components, not instant slicing.
