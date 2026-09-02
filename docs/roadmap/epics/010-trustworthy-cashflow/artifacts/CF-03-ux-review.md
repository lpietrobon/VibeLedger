# CF-03 — partial UX review and resume point

2026-09-02. This is a **source-based heuristic review**, not user research or a
completed browser walkthrough. Reviewed source against application revision
`d4e6871` (application code unchanged from `3b9c8c9`). The execution environment
became unavailable during synthetic preview startup; no page screenshot or runtime
interaction result was captured. CF-03 remains blocked, not done.

## Prioritized observations and intended fixes

| Priority | Evidence / problem | Required experience | Task |
|---|---|---|---|
| High | CF-01 probe demonstrates pending spend and premature transfer exclusions | Show posted spending with candidate uncertainty clearly included; review can explain the changed total | CF-06/CF-07/CF-08 |
| High | React spending uses a monthly category-comparison query regardless of selected granularity | Monthly/yearly total, category comparison, and clicked rows share the same dates and accounting scope | CF-08 |
| High | Draft inventory identifies missing period/spend filters and stale queries after mutations | Drill-down represents all contributing rows; correction refreshes total, categories, attention count and details | CF-08/CF-09 |
| High | Latest transaction date is used as an as-of date while completeness is not established | Report calendar bounds; qualify coverage rather than imply every account is current | CF-08 |
| Medium | Transfer candidates, refunds and reviewed status are distinct concepts | Explain evidence, candidate vs confirmed state, and durable correction; do not label suspicion as proven fraud | CF-09 |
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

## Resume walkthrough

1. In a fresh checkout of `pr-22`, use the disposable data pattern in
   [the audit probe](CF-01-accounting-probe.py). The temporary preview attempt was
   not committed and may be lost; recreate it without touching a real DB.
2. Run existing React and Streamlit surfaces against synthetic data and record
   what is actually rendered. Inspect monthly, yearly, category increase,
   subscriptions, transfer confirmation/rejection, and recategorization.
3. Exercise refresh, empty/incomplete-history state, negative categories, mobile
   layout, keyboard focus, accessible labels and failure feedback.
4. Append actual observations/screenshots or concise walkthrough notes here,
   separating them from these source inferences. Rank only necessary corrections
   and hand the final list to CF-08/CF-09. CF-11 remains independent acceptance.

No new interviews or broad redesign are necessary. The missing requirement is
actual supported-surface walkthrough evidence, not another round of product scoping.

## 2026-09-02 — second bounded attempt

A disposable synthetic server was started successfully in the execution runtime, and Chrome bootstrap succeeded. The helper's single navigation to the loopback preview timed out after approximately 311 seconds and was aborted. No page content/DOM loaded and no runtime UX observations were available; Streamlit was not inspected. No production data or service was involved. The helper has stopped. Resume only with a functioning preview/browser connection; the cause of this connection timeout is not established. Earlier source-level findings remain useful but do not satisfy the walkthrough criterion.
