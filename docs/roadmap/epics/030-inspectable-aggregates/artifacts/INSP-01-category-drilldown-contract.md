# INSP-01 — shared spending-category drilldown contract

## Canonical destination

`categoryDrilldownHref` creates the one Activity destination for an aggregate:

- `category`: exact effective category; parent matching remains an explicit
  `category:` search expression and is never substituted silently.
- `query=is:spend`: posted-spending semantics, retaining category-netted
  refunds and unconfirmed candidates while excluding pending rows and confirmed
  transfers through the shared server expression.
- `startDate` and `endDate`: inclusive source-provided reporting bounds; the
  helper never selects today.
- `sort=date&order=desc`: stable server ordering, with transaction ID as the
  deterministic tie-breaker.
- Optional `source` and `comparison` communicate origin/current-versus-
  comparison context in Activity without being sent to the accounting API.

Activity hydrates these fields from the URL, displays an active exact-scope
message when source context is present, and sends category/query/bounds/sort to
the paginated server request. It does not derive aggregate membership from a
client page.

## Evidence

- `frontend/src/lib/categoryDrilldown-contract.test.ts` covers canonical
  parameters and optional context.
- PI-13's immutable cross-page fixture verifies exact and parent scopes, signed
  spend parity, pending/transfer/refund handling, and more than one API page.
- Focused frontend and backend tests, typecheck, and production build passed.
