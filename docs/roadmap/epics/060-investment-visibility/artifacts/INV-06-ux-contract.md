# INV-06 Investments visibility and navigation contract

Status: frozen 2026-11-18, source design review on `a8370a2`.

## Information architecture

`/investments` is the dedicated landing route. It shows value cards, account rows, holdings (including an explicit brokerage-cash row), and an observed valuation history table/chart. Cards and rows use the same selected account IDs and exact date bounds. Gain/return areas are reserved but rendered as “Not available” until the contribution/valuation contract is implemented; absence is never zero.

Filters are All investments (default), Taxable, Tax-deferred, Roth, and explicit accounts. The API owns totals and money arithmetic. Every response discloses currency, exact requested/effective bounds, as-of, provenance, completeness, and coverage. Unsupported currency, missing valuation, stale sync, and partial coverage are visible qualifications rather than silently excluded values.

## States and accessibility

Not connected: explain that no investment account is linked and provide a link to Accounts. Empty: connected but no observed valuation, with no zero card. Error: retain last-good data and expose the error/last successful as-of. Stale and unsupported data are labelled inline. Controls are native labelled selects, buttons, and links, keyboard reachable with visible focus; the history table is the accessible alternative to the chart and includes exact dates.

## Navigation decision

Investments takes the Overview navigation slot (`/overview` remains a bookmarked compatibility route that renders Investments). Net worth remains reachable at Accounts, spending summaries at Spending, and all needs-attention rows at the existing Overview/Transactions drilldowns. The overview API remains unchanged.

Desktop uses a top-nav Investments item; mobile uses the same item in the bottom nav. The default app route `/` remains Spending. No review or net-worth workflow is removed.

## Date contract

Use TIME-01 exact date-only bounds and TIME-03 shared selector semantics: YTD (`current-year`), 1Y (`last-365`), 3Y (server-supported when coverage exists), Since tracked (`all` but disclose first observed date), and Custom. Transaction history does not imply valuation coverage. The effective range and first/last observed valuation dates are shown beside the history.
