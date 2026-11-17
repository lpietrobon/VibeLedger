# TIME-02 frozen RED baseline

2026-11-16; production source baseline `4ba04b6`. Author: time_contract_tests (not TIME-03 implementer). No application code changed.

Command from frontend:

```sh
TZ=America/Los_Angeles ./node_modules/.bin/vitest run src/lib/time-02-contract.test.ts src/components/finance/time-02-selector.test.tsx src/lib/dateRange.test.ts src/components/finance/date-controls-ux.test.tsx
```

Result: exit 1; **15 failed, 21 passed (36)**; 3 files failed, 1 passed. [Exact output](TIME-02-red-output.txt).

New tests expose forced comparator serialization (including actual fetch URL), missing independent selector/From–To, forced comparator on preset, missing date labels/unequal-duration disclosure. Existing boundary/clipping/overlay tests remain green. Literal tests cover leap, Jan 31, rollover, invalid date, reversed/half-empty, empty history, future explicit dates, all-time, UTC-midnight and DST under injected dates. Empty-history adapter assertions do not claim numerical backend coverage (TIME-04 owns real ledger fixtures).

## Explicit oracle migration before freeze

As announced in TIME-01, recovered old tests asserted semantics contrary to the epic. dateRange.test.ts now supplies explicit comparator where it expects one, preserving exact date oracles. date-controls-ux.test.tsx now expects independent controls and preserves None for custom, instead of asserting absence and forced previous-period. No arithmetic oracle changed. New frozen tests are time-02-contract.test.ts and time-02-selector.test.tsx. Do not modify their expected values to make implementation green.

Node dependencies reused by local untracked symlink to canonical frontend/node_modules; no package change. Full-suite clock tests must run with TZ=America/Los_Angeles as documented. Backend window validation is already present; cross-screen API coverage, pagination/evidence parity and URL persistence belong to TIME-04/05. The contract is accepted for TIME-03 implementation; independent final review remains TIME-06.
