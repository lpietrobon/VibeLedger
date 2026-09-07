# CF-01 — existing cashflow audit

Audited 2026-09-02: published `pr-22` at
`f5ec7b167514f6665459f95e3ffd01f4c6d04687`; application code is unchanged from
`3b9c8c922b7db22597a7ac74c3b3bb63554a820c`. The separate unpublished draft is
identified by [its manifest](CF-01-draft-manifest.json). A bounded read-only helper
inspected provider/account lifecycle paths; the coordinator traced accounting
paths and reproduced the baseline defects. No live financial data was accessed.

## Import and account coverage

| Area | Observed support | Limitation / treatment |
|---|---|---|
| Ingestion | Plaid Link, transaction sync, explicit historical import in `plaid_client.py`, `connect_service.py`, `sync_service.py`, and API routes | No CSV/manual/Venmo-specific importer or other provider adapter |
| Accounts | Provider account types/subtypes and IDs are stored generically | Checking/card/payment accounts can participate if Plaid actually supplies their transactions. A synthetic account named Venmo proves nothing about live coverage |
| Investment/partner accounts | Matching operates across stored account IDs, not owner identity | Treat a linked account as a possible internal-transfer counterparty; no holdings, performance, or investment analysis is needed |
| History | Link requests 730 days; explicit historical route paginates provider results | Request size is not a completeness guarantee. Sync success/counts/cursor and earliest/latest rows do not prove an entire period or every account is covered |
| Repeated ingestion | Provider transaction ID has a uniqueness constraint | Same-ID replay is distinct from two real same-amount purchases. Baseline ignores replays in added records and incompletely applies modifications; draft upserts and preserves real distinct IDs |
| Relink / repeated coverage | Provider account ID is unique; saved fingerprints can reapply annotations after removal/relink | Different provider IDs for the same real account are not automatically merged. Do not link overlapping copies concurrently and describe the combined result as verified; identify and explicitly remove duplicate coverage through existing account management, with backup and review |
| Currency | Account currency and raw transaction currency are stored | Aggregates currently sum nominal amounts without conversion/grouping. Mixed/unknown currency must be qualified or refused, never advertised as a meaningful single-currency total. No FX subsystem is proposed |
| Removal | Item removal deletes related rows while retaining annotation fingerprints; provider sync removals clean dependent rows | Fingerprints are best-effort identity fallback, not proof of account ownership. Draft expands cleanup and collision handling; preserve user decisions and test lifecycle behavior before landing |

Code references: `PlaidClient.create_link_token`, `get_accounts`,
`sync_transactions`, `get_historical_transactions`; `Account`, `Transaction`,
`SyncState`, `SyncRun`, `AnnotationFingerprint`; `SyncService.sync_item`,
`sync_historical`, `_apply_changes`, `_delete_dependent_rows`, `_reapply_fingerprint`;
`routes.remove_item`. Actual institution coverage requires an authorized live
account check and is explicitly unverified, not an audit completion blocker.

## Calculation and UI inventory

| Concern | Published behavior | Draft / remaining work |
|---|---|---|
| Posting and pending | `Transaction.date` receives the provider posting date; pending is stored, but realized analytics include pending rows | Draft shared posted filter addresses this; CF-07 |
| Transfer identity | `transfer_detector` pairs equal opposite amounts across accounts by nearby dates; paired rows are excluded before confirmation | Draft keeps candidates counted and validates confirmed/manual pairs; CF-06 |
| Corrections/sync | Modified records do not refresh every identity/date field or every derived relationship; failure handling can persist partial changes | Draft upsert, pending replacement, savepoint rollback and relationship cleanup; CF-05 |
| Categories | Manual override, stored rule, mapped provider category, uncategorized fallback | Draft sync rule application and matched-refund category parity; preserve simple precedence in CF-02/CF-07 |
| Refunds | Manual choices and conservative exact-match/provider-code detection exist; likely/confirmed refunds reduce expense | Draft removes ambiguous/multiple reuse and aligns purchase categories; cross-period and negative totals need contract coverage |
| Recurring | Deterministic cadence/amount summaries and persisted kept/canceled/auto overrides already exist | Clock-dependent baseline test failures are fixed in drafts. Do not add trials or price-change intelligence; CF-09 verifies existing behavior |
| Questionable transactions | Attention counts, annotation/review filters and transfer queue exist | No general duplicate-charge/fraud detector established. Preserve distinct charges and review evidence without claiming unsupported detection; CF-03/CF-09 |
| API and SQL | Analytics routes compute aggregates; `effective_transactions` supplies resolved fields; Streamlit joins transfer pairs and performs additional filtering | Draft shares accounting policy and adds API/SQL/drill-down parity tests; CF-07 |
| React | Overview/spending/transactions/transfers and recurring summaries use API results | Yearly category comparison requests monthly data; drill-down scope and mutation caches can disagree. Draft corrections need CF-03/CF-08/CF-11 review |
| Streamlit | `Spend.py`, `dashboard_lib.py`, spending/cashflow/transfer/transaction pages | Defaults and calendar anchoring can mislead; draft shared periods/filters require supported-surface walkthrough |

## Reproduced trace and baseline checks

[The probe](CF-01-accounting-probe.py) creates only a disposable synthetic DB and
prints [these baseline observations](CF-01-baseline-probe.json). Run it from the
repository root using the project's Python environment. It traces persisted rows,
the effective SQL view, four aggregate APIs, and a proposed spending drill-down.
This script is an audit probe, not an application test that asserts buggy output.

| Scope | Correct posted income / expense / net | Published API result |
|---|---|---|
| Salary, card/payment purchase, refund, confirmed funding, unconfirmed card repayment, pending rows | 2,200 / 305 / 1,895 | 2,500 / 1,104 / 1,396 |

The stored SQL evidence retains the two pending rows and an unconfirmed pair.
Baseline aggregates include pending amounts and exclude that pair, producing the
wrong figures. Overview also anchors its report date to the last transaction
(March 5) instead of the chosen clock (March 15). Baseline `q=is:spend` yields zero
rows because that filter is not yet supported. Draft regression tests use explicit
expected figures and exercise the corrected paths.

Backend baseline: **156 passed, 2 date-dependent recurring failures**, statements
**83.93%**, branches **71.64%**, combined **81.34%** over `app/` with no excluded
lines. [Original log](CF-04-baseline-backend-tests.txt).
Baseline frontend was checked separately in this audit:
[test log](CF-01-baseline-frontend-tests.txt).
Draft evidence already captured: **210 passed, 1 scheduler failure**, combined
**86.05%**; frontend **48 tests / typecheck / build passed**. See
[the recovery report](CF-01-recovered-progress.md) for commands, denominators, and
the explicit distinction between draft tests and independent acceptance.

## Minimal prioritized work and reuse decision

1. **High: fix realized scope and reconcile conservatively** — CF-06/CF-07. Reuse
   the shared posted accounting, pairing, refund and parity-test drafts after the
   CF-02 contract review. Preserve unresolved rows; never deduplicate actual charges
   merely by amount/date/name.
2. **High: make import lifecycle repeatable** — CF-05. Reuse focused sync/provider
   tests and atomicity/annotation corrections. Resolve the multi-item scheduler
   mock/identity failure before integration; do not weaken account ownership checks.
3. **High: align periods, categories, drill-downs and refresh** — CF-03/CF-08/CF-09.
   Reuse targeted frontend/Streamlit drafts, subject to a walkthrough. Label
   comparisons as recorded data and coverage unverified when proof is unavailable.
4. **Medium: expose unsupported scope honestly** — CF-05/CF-07/CF-08. Repeated-link
   copies and mixed currency remain limitations requiring explicit handling. A
   truthful warning or refusal is sufficient; automatic account merging, provider
   connectors, FX, and a new history-completeness subsystem are unnecessary here.
5. **Acceptance gates** — CF-04 tests/CI, CF-10 independent ledger verification,
   CF-11 independent UX verification, CF-12 maintainability, CF-13 handoff. Reuse
   existing harnesses; no second testing framework or agent API platform.

The audit is complete when these facts and gaps are recorded, not when all fixes
are implemented. No task needs supersession: the existing tasks cover the findings.
CF-02 and CF-03 are next eligible; prioritize closing CF-02, then CF-04 so focused
implementation can land behind tests. Keep the original patch immutable and port
only reviewed slices; its older documentation conflicts with the current roadmap.
