# PI-25 — fixed-clock date-formatting contract

## Frozen contract

With `2026-09-18T12:00:00Z` as the injected reference date:

- A date in 2026 renders as `D Mon` (for example, `2 Sep`).
- A prior or future year renders as `D Mon, YYYY`.
- Date-only inputs retain their written calendar date in every host timezone.
- Leap-day and year-boundary inputs are valid calendar dates; invalid, empty, and
  missing inputs render `—`, never an invalid browser string.

The contract is encoded in
`frontend/src/lib/format-date-tdd.test.ts`. It deliberately excludes chart axes
and tooltips, whose density-oriented format remains independent.

## Red-to-green evidence

- Red: `npm test -- --run src/lib/format-date-tdd.test.ts` — 4 failed against
  the former month-first/no-year formatter.
- Green: the same command — 4 passed after the shared formatter change.
- Regression: `CI=1 npm test -- --pool=forks --maxWorkers=1 && npm run typecheck
  && npm run build` — passed.

## Caller audit

The shared formatter is used by Activity rows and detail, `TransactionRow`,
`AnnotationSheet`, Transfer Detection, and Recurring. Account-linking session
copy is time-only, so it is outside this ordinary-date contract. Chart-specific
date formatting remains excluded.

Expected output and edge-case policy are frozen for independent PI-26 review.
