# TIME-01 frozen date contract

Source inventory: `4ba04b6`, 2026-11-16. This is a contract, not a claim that recovered code satisfies it.

## Inventory and migration

| Surface | Current source and behavior | Required preservation/change |
| --- | --- | --- |
| Overview | routes/index.tsx, shared selector, explicit month/previous-month; overview, cashflow-trend, category comparison, recent transactions | Keep initial comparison, net-worth current snapshot and all-history review queue distinct from selected-period flows. Exact bounds for flows/drilldowns. |
| Spending | routes/spending.tsx, shared selector; spending-summary, cumulative-spend, category comparison, timeline-spikes, spending-day, transactions | Keep initial month/previous-month; selected bounds drive summary/category/activity. Historical pace overlays are a separately labeled 0–3 completed-period context, not KPI comparison. |
| Insights | routes/insights.tsx, shared selector; cashflow-sankey, category-movers, timeline-spikes | Keep initial last-30/previous-period. Sankey/heatmap use selected range; movers absent for None. |
| Transactions/Activity | routes/transactions.tsx, All-time default; startDate/endDate URL and query/category/filter/source/sort/order | Keep all filters and date-only bookmarks. Shared control hides comparison. Explicit bounds authoritative; no silently substituting today. |
| Accounts | routes/accounts.tsx | Current balances/freshness; not date-filtered. No selector; account balance must not look historical. |
| Recurring | routes/recurring.tsx | Current detected commitments, historical evidence links; preserve existing API date support but no new page selector. |
| Transfers/review/settings | respective routes | Operational lists, not aggregate date scopes. Preserve date-specific transaction links. |
| Investments (future) | INV-06 onward | Reuse date semantics for observation/history, not current account snapshot. Coverage starts at actual observations, not transaction-history start. |

Shared `lib/dateRange.ts` already contains types/arithmetic; `DateRangeSelector.tsx` already provides presets and a two-tap calendar. Defects: rangeQuery ignores comparison; selector forces comparison and hides its control; custom From/To fields absent. `lib/api/client.ts` maps camelCase to snake_case; server `_explicit_comparison_bounds` validates explicit windows and treats omitted comparison as None. Legacy granularity-only requests retain legacy defaults. Tests with TIME-02 names in source are recovered implementation tests, not proof of this plan's red baseline.

## Domain and clock

Retain `DateRange = {startDate,endDate}` and `DateRangeSelection` with independent `ComparisonRule = none | previous-month | previous-year | previous-period`. ISO Gregorian day strings are inclusive posted-ledger dates, never UTC instants. Inject date-only today into pure helpers; `localToday(now)` derives it from the user's browser local timezone (tests run TZ=America/Los_Angeles with explicit offset instants). UTC arithmetic on parsed day components is permitted; UTC slicing the current instant is not. DST changes never change day counts.

Empty bounds are valid only together in All-time Activity; analytics need both endpoints. Invalid days, reversed/half-empty ranges are rejected without issuing requests. Accept future explicit dates without clipping; show recorded activity only, never forecast. Finite analytics windows preserve backend limit end-start <= 3660 days; long Activity queries remain paginated. Comparison limits obey the same bound. No monetary calculations in browser.

## Literal examples

Injected today 2026-10-25: Current month 2026-10-01–2026-10-25; Current year 2026-01-01–2026-10-25; Last 30 2026-09-26–2026-10-25; Last 365 2025-10-26–2026-10-25. Custom 2026-10-05–2026-10-15 stays exact. Previous month maps it to 2026-09-05–2026-09-15; previous year to 2025-10-05–2025-10-15; preceding equal period to 2026-09-24–2026-10-04; None emits no comparison fields.

Calendar mapping shifts each original endpoint independently, clipping invalid month days: 2026-03-29–31 maps to 2026-02-28–28 (3 vs 1 day, disclose unequal duration). Leap 2024-02-29–03-04 maps to 2023-02-28–03-04. Equal-duration mapping uses inclusive length, ends day before selected start. No recursive clipping for multi-period overlays. Calendar comparisons may overlap long custom windows; do not silently convert them to equal-duration.

## Control and compatibility

Five presets plus visible From/To fields; selecting a preset displays actual resulting endpoints. Separate accessible Comparison rule select with four choices. Changing range preserves explicit comparison; custom does not invent one. Initial helper defaults to None; pages may explicitly choose existing defaults. All-time clears comparison. Transactions hides rule control. Keep keyboard-friendly native inputs, calendar optional; invalid intermediate input must not fetch.

Dates and comparison must survive refresh/back on date-filtered pages; preserve existing camelCase startDate/endDate bookmarks and unrelated params. Existing 90d, YTD and last-month bookmarks with explicit endpoints remain literal Custom ranges, not newly evaluated rolling dates. No evidence of currently consumed preset URL tokens; do not invent a parser that changes unknown query parameters. Unbounded historical API requests remain compatible. Future INV 3Y/Since-tracked extensions must supply literal endpoints and explicit coverage.

Show actual selected and mapped comparison bounds, including year, independently of preset labels. Disclose differing inclusive durations and incomplete coverage. Missing history is unknown/not comparable, not zero growth. Server reporting evidence owns coverage and qualification; browser never infers completeness from first transaction. Pace overlays explicitly say historical full periods, may remain when KPI rule is None, and must not be mistaken for selected comparison; zero overlays does not change KPI rule.

## TDD migration and success gates

Intentionally replace old test claims that preset automatically implies KPI comparison, Custom forces previous-period, or comparison/From–To controls must be absent. Preserve old math/overlay expectations by supplying explicit previous-month/year/period in those fixtures. This is an announced contract correction, not weakening a frozen test after implementation. New TIME-02 tests freeze before TIME-03 code changes. TIME-04 adds real ledger parity, routing/back/refresh, coverage, and all screen integration; TIME-06 independently verifies. No accounting/category/transfer changes, chart redesign, global shared state, live ingestion or deployment.
