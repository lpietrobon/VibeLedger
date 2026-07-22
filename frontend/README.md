# VibeLedger Frontend Prototype

This is a controlled import of the Lovable first draft from `lpietrobon/vibeledger-vision` at commit `177a4fca110049b4777875d7683840770edf855e`.

It is intentionally a plain Vite React app, not the raw Lovable/TanStack Start scaffold.

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
npm run build
npx tsc --noEmit
```

## Current State

- Uses real VibeLedger data through the same-origin `/vibeledger/api` proxy.
- Pages: Overview, Spending, Transactions, Accounts, More.
- The frontend preview service builds the app, serves `/vibeledger/frontend/`, and proxies API calls to the local FastAPI service without exposing the bearer token to the browser.
