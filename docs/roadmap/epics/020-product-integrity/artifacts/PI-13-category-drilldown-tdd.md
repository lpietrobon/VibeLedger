# PI-13 — category drilldown TDD contract

## Privacy boundary

The fixture uses synthetic dates, amounts, account names, merchant labels, and
identifiers only. It does not encode live ledger observations.

## Fixture and arithmetic

The machine-readable source is `PI-13-category-drilldown-fixture.json`. Its
reporting period is inclusive, `2032-04-01` through `2032-04-30`.

The exact effective category aggregate is `FOOD/OTHER`:

```text
posted charges       40 + 25
confirmed refund             -10
unconfirmed candidate         12
pending row                  excluded
confirmed transfer           excluded
                         --------
exact signed spend total       67
```

The exact `is:spend` Activity population is the four rows
`food-charge-1`, `food-charge-2`, `food-refund`, and `candidate-out`. The
fixture also contains `FOOD/DINING` child activity. A parent `category:FOOD`
search intentionally includes that child, producing five rows and a signed
total of 87; a drilldown for the exact `FOOD/OTHER` aggregate must not broaden
to the parent.

The exact result is split over two API evidence pages of two rows each, in
stable descending date/id order. The pending row, confirmed transfer pair,
and candidate incoming leg are not in the spend set. The candidate outgoing
leg remains counted until reviewed, as required by CF-02.

## Frozen destination contract

Both Overview and Spending category aggregates must expose the same native
keyboard-operable link. In a production build its configured base path is
`/vibeledger/frontend`; the route suffix and query fields are:

```text
/transactions?category=FOOD%2FOTHER&query=is%3Aspend&startDate=2032-04-01&endDate=2032-04-30&sort=date&order=desc
```

The link must preserve the configured base path, exact effective category,
`is:spend` semantics, inclusive server reporting bounds, and stable default
sort/order. It must hydrate Activity's URL state and request the corresponding
category/date/query scope; the resulting pages, not the aggregate response,
are the source of truth for the expected IDs and signed amount.

## Tests

`tests/test_pi13_category_drilldown_tdd.py` exercises the actual backend
transaction search and category aggregate endpoints. It checks all evidence
pages, exact versus parent category behavior, and the independent arithmetic.
`tests/category_drilldown_fixture.py` seeds the fixture but does not call
analytics to derive its oracle.

`frontend/src/routes/category-drilldown-tdd.test.tsx` renders the actual
Overview, Spending, and Activity routes. It checks equivalent literal
destinations, URL hydration, request arguments, date bounds, and default
sorting. `frontend/src/lib/api/category-drilldown-tdd.test.ts` checks the real
API client's URL construction, including pagination parameters.

## Audited red result

The contract was authored against the pre-PI-02 implementation at local commit
`7273d56` on branch `roadmap/product-integrity-inspectability`. No production
code was changed for PI-13.

Focused frontend command:

```text
cd frontend && npm test -- --run src/routes/category-drilldown-tdd.test.tsx src/lib/api/category-drilldown-tdd.test.ts
```

Result:

```text
1 failed, 2 passed
```

The intentional failure is Overview's category comparison being rendered as
plain text rather than an inspectable link. The passing tests prove the
existing Spending link, Activity hydration/request state, and API client
construction. The backend contract command passed:

```text
pytest -q tests/test_pi13_category_drilldown_tdd.py
3 passed
```

Existing frontend tests excluding PI-13 passed (`54 passed`); typecheck and
production build passed; relevant CF-07/search backend tests passed (`54
passed`).

## Freeze rule

After review, the following are immutable PI-02/PI-14 contract files:

* `docs/roadmap/epics/020-product-integrity/artifacts/PI-13-category-drilldown-fixture.json`
* `tests/category_drilldown_fixture.py`
* `tests/test_pi13_category_drilldown_tdd.py`
* `frontend/src/routes/category-drilldown-tdd.test.tsx`
* `frontend/src/lib/api/category-drilldown-tdd.test.ts`

PI-02 and PI-14 may add separate coverage and repair production code, but may
not rewrite these fixture values or assertions. Any discovered contract error
must be escalated for review.

## Execution log

- 2026-09-11: Added the synthetic fixture/oracle and frozen backend and
  frontend contract tests. Production code was not changed.
- 2026-09-11: Focused frontend TDD is intentionally red (`1 failed, 2
  passed`) because Overview still renders category labels as plain text.
