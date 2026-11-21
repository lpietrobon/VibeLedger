# TIME-03 independent legacy oracle reconciliation

2026-11-17. Reviewer: `time04_tests`, separate from `time03_implementation`.
Application source reviewed: `9100f98e38976e4d0e2761c0cb858e5c21dc2f59`.

## Verdict: obsolete implicit-comparison oracle, not a production defect

The failing recovered test is `frontend/src/routes/spending-selected-day-ux.test.tsx`, “requests full prior years for Year while retaining YTD summary bounds”. After pressing Year, it expected summary comparison `2025-01-01`–`2025-10-25` without explicitly choosing previous-year. Spending initially selects previous-month. The independent contract makes range and comparison separate; Year must not replace that selected rule.

Frozen TIME-01 states:

> Changing range preserves explicit comparison; custom does not invent one.

And explicitly authorizes this migration:

> Intentionally replace old test claims that preset automatically implies KPI comparison ... Preserve old math/overlay expectations by supplying explicit previous-month/year/period in those fixtures.

The reviewed production behavior maps the YTD endpoints independently one calendar month backward: `2026-01-01` → `2025-12-01`; `2026-10-25` → `2026-09-25`. Long custom/calendar comparisons may overlap under TIME-01. This is not an arithmetic error.

## Minimal test-only reconciliation

Kept all existing prior-year overlay and numerical summary expectations. Added an explicit assertion that Year preserves previous-month and its literal endpoints, then changed the independent Comparison rule select to previous-year before the existing prior-year KPI assertion. The original previous-year arithmetic oracle is unchanged. No production code changed, and no frozen TIME-02 or TIME-04 test changed.

## Evidence commands

From `frontend`, with `TZ=America/Los_Angeles`:

```sh
./node_modules/.bin/vitest run src/routes/spending-selected-day-ux.test.tsx
./node_modules/.bin/vitest run src/routes/spending-selected-day-ux.test.tsx src/lib/time-02-contract.test.ts src/components/finance/time-02-selector.test.tsx src/lib/dateRange.test.ts src/components/finance/date-controls-ux.test.tsx
./node_modules/.bin/vitest run --exclude src/routes/time04-cross-screen.test.tsx
```

Before reconciliation: **1 failed / 3 passed**, exactly the implicit previous-year assertion. Source before/after reports are retained beside this artifact. TIME-04 is intentionally excluded from the existing-suite regression because it is the independently frozen RED baseline for future TIME-05 routing implementation, not a TIME-03 regression. This exclusion is not a claim that the complete branch is green.

After reconciliation: **40 passed** across the legacy slice and unchanged frozen TIME-02 suite.

Existing full frontend regression (excluding the intentionally RED TIME-04 file): **122 passed across 20 files**. Frozen TIME-02 source diff against `b3a0cae` is empty; frozen TIME-04 executable checksums remain unchanged. This resolves the sole reported TIME-03 regression and permits the coordinator to close TIME-03.

Final `tsc --noEmit`: passed. Roadmap scanner: 6 epics, 80 tasks, 0 issues. No deploy or live ingestion.
