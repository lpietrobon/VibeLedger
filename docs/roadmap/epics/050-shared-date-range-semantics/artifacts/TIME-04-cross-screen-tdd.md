# TIME-04 independent cross-screen frozen test contract

Author: `time04_tests`, separate from TIME-03 and TIME-05 implementers. Date: 2026-11-17.
Application source baseline: `9100f98e38976e4d0e2761c0cb858e5c21dc2f59` (TIME-03 shared controls completed while this independent test slice was authored). No production code or TIME-02 test changed here.

## Executable coverage

- `frontend/src/routes/time04-cross-screen.test.tsx`: actual Overview, Spending, Insights and Activity routes, actual shared selector and query hooks. Shell/account selection and provider I/O are stubbed, not date state or arithmetic. Covers literal historical bookmarks, unrelated query preservation, remount, browser popstate delivery, invalid/half-empty/reversed dates, keyboard-editable custom fields, four bounded presets at narrow width, three independent comparison mappings plus None, exact query bounds for all selected flow APIs, and complete Activity access beyond the first 500 rows. API request assertions do not pretend to verify monetary arithmetic.
- URL contract uses existing `startDate`/`endDate`, adding explicit `comparison=none|previous-month|previous-year|previous-period`; no date-preset parsing or global synchronization is required. Unrelated parameters must survive writes. Date-only legacy bookmarks remain literal Custom.
- `tests/test_time04_cross_screen_tdd.py`: real isolated SQLite ledger and real FastAPI endpoints. Extends existing independent category-drilldown fixture with 501 one-dollar charges and one explicit duplicate correction. Literal spend oracle is **$605 across 507 evidence rows** (500+7 pages): $40+$25-$10+$12+$20+$17+$501. Pending $999, confirmed $30 transfer and duplicate $40 excluded; unconfirmed $12 transfer candidate retained; refund netted to its expense category. Checks Overview, Spending, category totals, cashflow trend, timeline, cumulative pace and Sankey against that same independent amount. Explicit empty/prior-unavailable windows must not invent percentage growth.
- Existing frozen TIME-02 unit/selector tests retain leap/clipping/DST/all-time/invalid-control arithmetic coverage; existing `category-drilldown-tdd.test.tsx` and `test_pi13_category_drilldown_tdd.py` retain rendered category links and source-query membership oracles. `test_time_spending_windows.py` retains explicit API validation, aligned comparison/pace and posted-data cutoff coverage.

## Findings / required integration

Overview, Spending and Insights currently discard URL dates and comparison; Activity reads URL only at initial mount. All four lack a round-trip write/popstate contract. Malformed aggregate bookmarks therefore issue requests for unrelated default ranges. Insights incorrectly requests movers for bookmarked None because it ignores the bookmark. Activity renders only the first 500 filtered results without a way to reach remaining evidence. These are implementation work for TIME-05, not reasons to change the test expectations.

Server explicit-window support is already sufficient for the fixture's tested endpoints; no API migration is demanded merely to manufacture failures. Keep granularity-only compatibility and server money math. The shared URL-selection integration is the required migration.

## Commands and evidence

```sh
cd frontend
TZ=America/Los_Angeles ./node_modules/.bin/vitest run src/routes/time04-cross-screen.test.tsx
./node_modules/.bin/tsc --noEmit
cd ..
/home/skywalker/VibeLedger/.venv/bin/python -m pytest tests/test_time04_cross_screen_tdd.py -q
```

Backend: **2 passed**, one existing Starlette/httpx deprecation warning. Frontend: **36 failed / 20 passed (56)**, all failures behavioral assertions; no timeout or unhandled runtime error. Typecheck: **passed**. Frontend final output is retained in `TIME-04-red-output.txt`. Typecheck must remain clean; behavioral assertion failures are the intended RED state.

## Verification limits

Narrow-width jsdom and native input events test control/query behavior, not visual layout, touch hit targets or a real browser history stack. TIME-06 still owes actual narrow/wide browser and touch/keyboard inspection, performance and full regression runs. Popstate is dispatched with literal alternate bounds to test the route subscriber, not to claim browser automation. No deployment, live ingestion, production database access or provider call occurred.

## Frozen executable SHA-256

- `frontend/src/routes/time04-cross-screen.test.tsx`: `70d2fcef710b2215a15626807d078bbfb5b81eaba8f2235e4983a31bfc6a9403`
- `tests/test_time04_cross_screen_tdd.py`: `270b9b70bc2ce54b10b689a940dcb1292305e85ba170fe968ebf0109cd22a868`

The 501-row DOM case has a 30-second test timeout to distinguish a behavioral missing-pagination failure from host-load timeout; it does not define a product latency acceptance threshold.
