# Spending accuracy audit — independent test-first RCA

## Baseline / scope

- Parent implementation branch: `implementation/spending-dates-and-timeline-spikes`, original head `28b5400709128233e278a28dee6dd36081f12ef8`.
- Independent red tests committed on audit branch at `2173cb1b15cca947fd7137f3d1f6882a0e8d51c6`.
- First CI red result: GitHub Actions CI run 40234182817, Python job; **3 failed, 311 passed**. Frontend and roadmap checks passed.
- The red tests' expected outputs use hand-computed signed transactions and fixed dates. Do not use production aggregation results to build expected values.

## Invariants and initial results

| Invariant | Baseline | Oracle |
|---|---|---|
| Eligible posted expenses reconcile among spending summary, Overview, category spend, Sankey, daily and cumulative timelines and **all** Activity pages | PASS | Oct 4–7: 100 + 35 + 100 - 35 = 200.00; previous September selected range 150; signed refund offsets, candidate transfers counted, confirmed transfers, pending and corrected duplicate excluded |
| Categories and transaction identities match | PASS | FOOD/OTHER 65, TRANSPORT/OTHER 95, SHOPPING 40, 7 exact eligible expense entries |
| Cumulative spend can decrease when refunds net against expenses | PASS | 100 → 135 → 235 → 200 |
| No comparison selected suppresses comparison delta even if history exists | PASS | change and percentage null |
| Unequal-duration calendar comparisons are truthfully disclosed | **FAIL** | March 29–31 has 3 dates; mapped February 28 has 1 date |
| Known monthly bill must not suppress another independent unusual charge on the same date | **FAIL** | $2,300 rent recurring plus $700 new dentist charge should annotate dentist |
| Seven observed positive-spend days across a 28-day window should not establish confident zero baseline | **FAIL** | Sparse history abstains |
| Attribution never exceeds spike's positive excess, including refund-offset cases | PASS | $900 excess; $2,000 charge capped to $900 (100%) |

## RCA and correction

### RCA-1. Duration mismatch hidden in comparison metadata
`comparison_reporting()` emitted an invariant fixed qualification even when selected inclusive current and prior windows differed in length. Month-end calendar clipping can compress 3 dates to 1. Corrective change: compute inclusive day counts and append an explicit **unequal** duration warning, without altering the user's chosen date alignment or normalizing totals implicitly.

### RCA-2. Recurring top charge suppressed independent expense
`detect_spikes()` identified the maximum transaction and, if it matched one month ago, set `recurring=True` and discarded **the whole day's anomaly**. Corrective change: identify candidate month-matched bills separately, add their expected amount to the day baseline and remove them from ranking of novel drivers. Also avoid treating a frequent daily/weekly merchant as a monthly recurring one just because it appeared 28 days ago. This is an explanatory heuristic, not proof of causality.

### RCA-3. Inadequate history treated as verified zero
The prior gate allowed just 7 positive-spend days out of a 28-day window; 21 missing/zero days drove the median to zero, then routine spending was called an anomaly. Corrective change: require at least 14 positive-spend days over the previous 28, plus the prior earliest-recorded requirement. Still disclose that the account's complete history is unverified. A more sophisticated confidence model may follow but shouldn't weaken this guard.

## Validation protocol

Run `python -m pytest tests/test_spending_accuracy_invariants.py tests/test_spike_interpretation_invariants.py tests/test_spk02_timeline_spikes_tdd.py -q`, then `python -m pytest -q`; also run `npm run typecheck && npm test && npm run build` under `frontend/`. Confirm the new tests pass **without editing the initial oracle**. Record passing CI runs and any residual correctness risks before recommending merging. Do not mark the roadmap's independent verification tasks complete unless an actual independent review is executed.

## Green verification after fixes

- Corrective commit: `014fef3ac01a4677462dac3ecf08881ea3e5b50a`.
- [CI run 40234433136](https://github.com/lpietrobon/VibeLedger/actions/runs/40234433136): Python, frontend typecheck/test/build succeeded.
- [Tests run 40234433159](https://github.com/lpietrobon/VibeLedger/actions/runs/40234433159): **316 Python tests passed** (one third-party deprecation warning), frontend tests/build and roadmap scanner succeeded.
- Duplicate PR-triggered jobs [40234437536](https://github.com/lpietrobon/VibeLedger/actions/runs/40234437536) and [40234437649](https://github.com/lpietrobon/VibeLedger/actions/runs/40234437649) also passed at the corrective commit.
- All initially failed test oracles remained unchanged. Two additional regression tests now pin that frequently occurring merchants must not masquerade as monthly bills, and ordinary rent alone must not be flagged.
- Remaining limitation: heuristic spike quality requires labeled real-world cases; passing independent numerical and control-flow invariants does **not** estimate detection precision/recall or guarantee that any causal contribution statement is true.
- No production migration, deployment, or independent human review is claimed.
