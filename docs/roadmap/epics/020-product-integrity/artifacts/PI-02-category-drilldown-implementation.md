# PI-02 — Shared category drilldown implementation

## Outcome

Overview and Spending category comparisons now expose the same inspectable
Activity destination. The shared builder preserves the configured frontend
base path and emits the exact effective category, `is:spend` scope, inclusive
server reporting bounds, and stable `date:desc` ordering.

Overview receives bounds from `reporting.currentPeriod`; when that metadata is
not available, the category labels retain the prior non-link behavior instead
of inventing a browser-clock period. Spending continues to use its existing
reporting metadata/fallback for its transaction list, while its category links
use the same shared builder as Overview.

## Contract evidence

The immutable PI-13 synthetic fixture remains unchanged. Its `FOOD/OTHER`
aggregate links to:

```text
/vibeledger/frontend/transactions?category=FOOD%2FOTHER&query=is%3Aspend&startDate=2032-04-01&endDate=2032-04-30&sort=date&order=desc
```

The unchanged PI-13 route test verifies that both surfaces produce this exact
destination and that Activity hydrates the corresponding request. The fixture's
four-row exact population and signed expense total of `67` are preserved; the
parent `FOOD` population remains intentionally broader at five rows and `87`.

## Files changed

- `frontend/src/lib/categoryDrilldown.ts` — shared destination contract.
- `frontend/src/routes/index.tsx` — Overview wiring to server current-period bounds.
- `frontend/src/routes/spending.tsx` — Spending wiring to the shared builder.

No Sankey or Movers route was implemented as part of PI-02.

## Verification

- Focused immutable contract: 3 tests passed.
- Full frontend suite: 57 tests passed.
- Typecheck: passed.
- Production build: passed.
- Relevant backend category/search/reporting/accounting suite: 63 tests passed.
- PI-13 fixture, tests, and artifact were not modified.
