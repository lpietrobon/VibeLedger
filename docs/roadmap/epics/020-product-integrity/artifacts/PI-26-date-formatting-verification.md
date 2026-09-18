# PI-26 — date-formatting verification

## Tested implementation

- Commit: `765082b` (`Standardize current-year-aware date formatting`)
- Immutable oracle: `frontend/src/lib/format-date-tdd.test.ts`
- Oracle comparison: no changes to that test file after the tested commit.

## Independent checks

- `npm test -- --run src/lib/format-date-tdd.test.ts` — 4 passed.
- `npm run build` — passed.
- Caller audit confirms `formatDate` is the sole ordinary-date formatter for
  Activity, detail, annotation, Transfer Detection, and Recurring.
- Calendar heatmap is chart-specific and intentionally retains its own UTC
  date machinery. Account-link session copy is time-only. API query dates and
  date-input values remain raw machine-readable ISO strings.

## Verdict

The frozen fixed-clock contract passes unchanged. Calendar parsing prevents
timezone rollover; invalid or absent values use a presentational fallback. No
repair was needed during verification.
