# PI-14 — category drilldown independent verification

## Verdict

PASS. PI-02 satisfies the frozen PI-13 category-drilldown contract at
integrated commit `7db4582` (`Implement shared category drilldowns`). No
PI-13 fixture, test, or accepted assertion was changed.

## Independent aggregate/population evidence

The synthetic PI-13 ledger was seeded into a clean test database and queried
through the production API. The reporting date was explicitly
`2032-04-30`; the server supplied inclusive current-period bounds
`2032-04-01` through `2032-04-30`.

The `FOOD/OTHER` source aggregate used by both Overview and Spending was:

```text
current category value: 67
```

The full exact-category Activity population was fetched in two pages using
`q=is:spend`, `category=FOOD/OTHER`, and the inclusive bounds:

```text
page 1: candidate-out  12, food-refund -10
page 2: food-charge-2  25, food-charge-1 40
literal signed total: 12 - 10 + 25 + 40 = 67
```

This is the same population and total represented by the Overview and
Spending category value. The API’s server ordering was the expected stable
`date DESC, id DESC` ordering.

The independently checked parent search (`category:FOOD`) intentionally
broadened to five spend rows, including `food-child`, with signed total `87`.
The exact drilldown remained four rows and did not broaden to the parent.

The fixture semantics were preserved: the confirmed refund contributes `-10`,
the pending row is excluded, the confirmed transfer pair is excluded, and the
unconfirmed candidate outgoing leg remains counted while its incoming leg is
not in the spend population.

## UI and navigation checks

- Overview obtains its link bounds from `reporting.currentPeriod`; it does not
  use the browser clock when server bounds are present.
- Spending obtains the same server current-period bounds and uses the same
  `categoryDrilldownHref` helper.
- Both surfaces produce the identical literal destination, including exact
  effective category, `is:spend`, inclusive dates, `sort=date`, and
  `order=desc`.
- The configured Vite base path (`/vibeledger/frontend`) is preserved.
- Activity reads the destination on reload, hydrates category/query/date/sort
  state, and requests the exact server scope.
- CategoryComparison uses a native visible anchor, so keyboard focus and
  activation are provided without a mouse-only handler.
- Empty comparison data renders an empty comparison list; comparison and
  Activity request failures render the existing `role=alert` messages; an
  empty Activity population renders the existing no-match state.

One presentation nuance was recorded but not treated as a contract failure:
the Activity renderer keeps equal-date rows in deterministic ascending ID
order, while the API’s default tie-break is descending ID. The accepted
fixture has distinct dates for its four spend rows, and the difference cannot
change the destination population or signed total. No unrelated selection
behavior was changed during this verification.

## Verification commands

```text
python -m pytest -q tests/test_pi13_category_drilldown_tdd.py
3 passed

cd frontend && npm test -- --run src/routes/category-drilldown-tdd.test.tsx src/lib/api/category-drilldown-tdd.test.ts
3 passed

python -m pytest -q tests/test_pi13_category_drilldown_tdd.py tests/test_cashflow_reporting.py tests/test_reporting_response_contract.py tests/test_insights_analytics.py
63 passed

cd frontend && npm test -- --run
57 passed

cd frontend && npm run typecheck
passed

cd frontend && npm run build
passed

python -m pytest -q
267 passed

git diff --check
passed
```

The immutable PI-13 files have an empty diff against the PI-02 implementation
parent. No production code or frozen test contract required repair.

## Execution log

- 2026-09-11: Independently verified the integrated PI-02 implementation
  against the frozen PI-13 frontend and backend contract. Re-derived the
  aggregate and complete paginated Activity population from a clean synthetic
  ledger; exact and parent category totals matched the independent oracle.
- 2026-09-11: Verified server-bound dates, base path, reload hydration,
  keyboard-operable links, transfer/refund/pending semantics, and existing
  empty/error branches. Recorded the equal-date presentation tie-break nuance
  as non-blocking because it does not affect the accepted population or total.
