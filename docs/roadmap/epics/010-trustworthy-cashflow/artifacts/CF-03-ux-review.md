# CF-03 — spending and reconciliation UX review

Completed 2026-09-07 against application revision `c085d36`. This is a focused
researcher walkthrough, not an interview or usability study. Runtime evidence comes
from disposable synthetic data rendered through React/jsdom and Streamlit AppTest;
source inspection supplied implementation context. No real financial data was used.
The hosted browser blocks loopback (`ERR_BLOCKED_BY_CLIENT`), so screenshots and
visual responsive-CSS claims are deliberately not made.

## Prioritized observations and intended fixes

| Priority | Evidence / problem | Required experience | Task |
|---|---|---|---|
| High | The top-right sync icon is a button with no click handler | Sync invokes the existing API, reports progress/success/failure, and refreshes all report data affected by a completed sync | CF-08 |
| High | CF-01 probe demonstrates pending spend and premature transfer exclusions | Show posted spending with candidate uncertainty clearly included; review can explain the changed total | CF-06/CF-07/CF-08 |
| High | React spending uses a monthly category-comparison query regardless of selected granularity | Monthly/yearly total, category comparison, and clicked rows share the same dates and accounting scope | CF-08 |
| High | Draft inventory identifies missing period/spend filters and stale queries after mutations | Drill-down represents all contributing rows; correction refreshes total, categories, attention count and details | CF-08/CF-09 |
| High | Latest transaction date is used as an as-of date while completeness is not established | Report calendar bounds; qualify coverage rather than imply every account is current | CF-08 |
| High | Both presentations put net worth before spending in the desktop metric order | Spending and its prior-period comparison are the first decision-facing values; balances remain secondary | CF-08 |
| Medium | Transfer candidates, refunds and reviewed status are distinct concepts | Explain evidence, candidate vs confirmed state, and durable correction; do not label suspicion as proven fraud | CF-09 |
| Medium | Streamlit manual-transfer selectors offer the same unfiltered rows as both outflow and inflow, and the list can remain stale after an action | Constrain opposite-signed legs, prevent self-pairing, and visibly refresh or confirm completion | CF-09 |
| Medium | Negative refund categories are possible under accepted CF-02 | Preserve signed values or show a simpler faithful view; never silently clip to invent a balanced flow | CF-08 |
| Medium | Subscription summaries already exist; duplicate/fraud detection support is limited | Show active subscriptions, estimated costs and evidence; inventory supported hints rather than invent detection | CF-09 |

Sources: `frontend/src/routes/index.tsx`, `spending.tsx`, `transactions.tsx`,
`transfers.tsx`, `frontend/src/lib/api/client.ts`, `Spend.py`, and
`pages/2_Spending.py`; [audit](CF-01-audit.md) and
[prior draft inventory](CF-01-recovered-progress.md).

## First view and review behavior

Lead with period spending and a clearly labeled comparison. Income/net and the
largest category changes support the explanation. Keep data coverage and unresolved
items visible as secondary context, without making synchronization the landing view.

An imported copy is an ingestion identity issue, not evidence that a merchant
charged twice. A repeated posted charge remains counted while reviewed. A transfer
candidate displays both sides and uncertainty; confirming an established pair
removes only its internal flows. A category correction moves allocation, not the
total. Feedback should show saved/failed state, retain failed edits, persist across
reload, and refresh affected views. Existing simple categories and explicit
confirm/reject controls are sufficient; routine reimbursement linking is not required.

## Runtime walkthrough notes

The checked-in React walkthrough (`frontend/src/routes/cashflow-ux-walkthrough.test.tsx`)
rendered the overview and spending routes with one current-month increase, an
uncategorized $777 card charge, attention counts, and prior-period data. It confirmed
that monthly and yearly summaries render, the attention item reaches a bounded
transaction view, and the questionable row opens an editor that exposes bank evidence,
current mapping, category/refund/review controls, and a save action.

The checked-in Streamlit walkthrough (`tests/test_cf03_streamlit_walkthrough.py`)
rendered Overview, switched Spending from Monthly to Yearly, and verified both runs
completed without UI exceptions against a disposable multi-account ledger containing
income, expenses, an internal transfer and an unreviewed charge. A separate AppTest
inspection of Transactions and Transfers confirmed the editor/action surfaces and
revealed the transfer-selector and stale-table issues above.

Commands from the repository root:

```bash
frontend/node_modules/.bin/vitest run frontend/src/routes/cashflow-ux-walkthrough.test.tsx
.venv/bin/python -m pytest -q tests/test_cf03_streamlit_walkthrough.py
```

Actual user feedback: the project owner reported that the top-right fetch/sync icon
appears not to work. Source inspection confirms that it has no handler. All other
findings are researcher inference from runtime output and source, not user testimony.

## Bounded handoff

CF-08 owns spending-first information order, one reporting scope across totals/charts/
rows, honest coverage/as-of language, signed refund-safe charts, visible query errors,
and a working sync control with report invalidation. Preserve a two-column mobile
summary and ensure period/sync controls have explicit accessible names and keyboard
activation.

CF-09 owns evidence and state in the review queue: distinguish imported identity,
repeated-charge suspicion, transfer candidate and category issue; constrain transfer
legs; make save/confirm/reject failures visible without discarding edits; refresh all
affected views; and expose recurring evidence without claiming unsupported fraud or
duplicate-charge detection. Dialogs and controls must remain labeled, keyboard
reachable, and usable in the existing mobile sheet/card layouts.

## Residual manual visual check

CF-11 should still inspect real narrow/wide layouts and keyboard focus order in a
reachable browser. This is a verification risk, not an unresolved CF-03 product
choice: the intended order, labels, feedback and evidence states are now specified.

## 2026-09-02 — second bounded attempt

A disposable synthetic server was started successfully in the execution runtime, and Chrome bootstrap succeeded. The helper's single navigation to the loopback preview timed out after approximately 311 seconds and was aborted. No page content/DOM loaded and no runtime UX observations were available; Streamlit was not inspected. No production data or service was involved. The helper has stopped. Resume only with a functioning preview/browser connection; the cause of this connection timeout is not established. Earlier source-level findings remain useful but do not satisfy the walkthrough criterion.
