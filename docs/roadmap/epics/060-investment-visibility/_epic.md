---
id: 060-investment-visibility
title: Investment account visibility and trustworthy performance
status: planned
owner: null
created: 2026-11-10
revision: 2
---

## Goal

Extend VibeLedger with a dedicated Investments area for Schwab and Fidelity taxable brokerage and tax-sheltered accounts: understand total value, money added/withdrawn, investment gain, pooled allocation, and eventually reliable returns across selected accounts and time windows. Reuse connections and account identity, not spending accounting. Read [the spirit](spirit.md) before changing scope.

## Scope and boundaries

- Keep investments as a separate domain inside the existing app, with dedicated securities, holdings, activity, valuation history, flow classification and performance services/API contracts. Reuse SQLite, encrypted connection storage, account identity and compatible snapshot infrastructure; no separate app or database platform is required.
- **Non-negotiable: connecting or syncing investments must not populate Spending charts.** Investment trades, dividends, interest, fees, reinvestments, cash sweeps, valuations and investment-account activity stay outside spending, household operating income/cashflow, recurring detection, merchant/category analytics and default spending Activity queries. Enforce this server-side at the canonical query boundary, not just in navigation or category labels. An existing include-transfers option must not bypass the investment-domain boundary.
- Bank-side funding/withdrawal rows remain inspectable with their original provenance. Reconciled checking-to-brokerage transfers are investment flows, not household expenses/income. Unresolved bank-side rows follow explicit review semantics: do not silently hide unrelated payments based on institution names, nor pretend uncertain flows are resolved. Link evidence across domains without copying investment events into the spending ledger. Never revive the legacy one-sided transfer override as a shortcut.
- Accounts/net worth may intentionally aggregate both domains, counting each account balance once; holdings must not be added again on top of those balances. Brokerage cash belongs inside its investment account. Mixed-product Items and cash-management accounts require account-level classification, not institution-wide exclusion.
- Use first-mile provider evidence before committing to coverage. Validate actual Schwab/Fidelity products, entitlements, taxable/IRA/Roth/workplace account coverage, billing, freshness, pagination and history. Prior research suggests access is possible; it is not proof of this user's access. Up to 24 months of activity is not historical daily valuations.
- Initial focus: USD portfolios. Unsupported currencies/assets must be visible and excluded or qualified explicitly, never silently summed. Account tax treatment can be unknown/correctable; portfolio deposits are not tax-year contributions, and rollovers are not annual contributions.
- Record observed valuations from first successful sync. Preserve as-of times, provenance (observed/imported/estimated), completeness and revisions. Define missing history and optional statement-import seams; extensive reconstruction is deferred. Never draw a zero balance for missing data or invent pre-link performance.

## Milestones and release gates

| Milestone | Tasks | User outcome / gate |
|---|---|---|
| M1 — Coverage and contracts | INV-01–02 | Evidence of actual provider/account coverage and an explicit accounting/domain contract; provider blockers stay visible |
| M2 — Isolated ingestion | INV-03–05 | Dedicated investment sync, holdings/activity and snapshots; independent proof that spending is not contaminated |
| M3 — Useful visibility | INV-06–09 | Account totals, holdings, freshness and observed value history in Investments; deliberate navigation decision |
| M4 — Contributions versus growth | INV-10–12 | Reconciled deposits/withdrawals and value-versus-capital chart with auditable dollar gain |
| M5 — Pooled allocation | INV-13–15 | Value-weighted stocks/bonds/cash/other/unknown, including editable fund splits |
| M6 — Returns and integrated handoff | INV-16–19 | Qualified money-weighted and time-weighted returns for portfolio/account selections and supported windows |

The milestones are incremental, not a promise to withhold balances until returns exist. Allocation can proceed alongside flow work after M3; returns require reconciled flows. Only INV-01 is initially ready. Estimates are deliberately not commitments; refine effort after M1.

## Accounting and performance contract

For the selected account set and period: **gain = ending value − starting value − deposits + withdrawals**. This is total investment gain (including income and relevant fees), not pure price appreciation; unresolved valuation/activity differences must be flagged instead of labeled as market performance.

| Event | Individual account | Selected portfolio containing both investment accounts |
|---|---|---|
| Checking → brokerage | External deposit | External investment deposit; not household spending |
| Schwab → Fidelity transfer/rollover | Withdrawal/deposit respectively | Internal; zero net external contribution |
| Buy/sell using brokerage cash | Internal trade | Internal trade |
| Dividend/reinvestment | Investment income plus optional purchase | Investment gain, not new capital |
| In-kind transfer | External flow at supported transfer value | Internal if both sides are selected; uncertain value blocks affected returns |

The boundary is the selected set, not all connected accounts. Store gross deposits and withdrawals as well as net flows. Use valuation and cash-flow timing conventions consistently; handle pending/corrected transactions, transfers in transit, account closure/relink, missing counterparties and missing prices explicitly.

Default overview: value, net added, gain dollars, and return only when reliable. The main line chart compares account value with **opening value + cumulative net contributions**, both anchored at the period's opening value. A companion monthly flow chart keeps deposits and withdrawals separately visible. Every number/chart drills into the same selected accounts, dates and underlying evidence.

Provide All investments by default, Taxable / Tax-deferred / Roth and individual/custom account selections. Use shared date semantics with YTD, 1Y, 3Y, Since tracked and Custom as supported; expose exact bounds and effective coverage, and do not offer unsupported history as valid. Money-weighted personal return (XIRR) answers how the user's money performed; time-weighted return answers performance independent of contribution timing and supports future benchmark comparisons. Never average account percentages. Label period versus annualized values, avoid annualizing short periods by default, and abstain on undefined/ambiguous results or inadequate valuation coverage.

Allocation uses economic exposure, not instrument type: a mutual fund/ETF label is not stock/bond allocation. Weight editable, sourced, dated fund splits by holding values, retain Unknown, and never imply automatic fund look-through. Automated exposure feeds and benchmarks are future work.

## Navigation proposal

The preferred candidate is **Investments replacing the largely redundant Overview tab**, not adding another duplicate summary page. This is a proposal to evaluate in INV-06, not approval to delete Overview now. Inventory each unique Overview function first: preserve net worth via Accounts, spending summaries via Spending, and needs-attention counts/exact drilldowns via a discoverable review surface. Specify default landing behavior, mobile navigation, old Overview URL handling and empty/not-connected states. If a unique function lacks a suitable home, retain Overview until it does. Do not remove the overview API merely because a tab moves.

## Dependencies and non-goals

- Preserve [trustworthy cashflow](../010-trustworthy-cashflow/_epic.md) invariants; do not expand that completed epic retroactively. M1 inventories current implementation rather than trusting old root-doc descriptions.
- Reuse [shared date-range semantics](../050-shared-date-range-semantics/_epic.md): INV-06 depends on TIME-01 for the contract and INV-08 on TIME-03 for the reusable implementation. This does not gate provider research or isolated ingestion. Update applicability documentation during integration without claiming the date epic is complete.
- Align evidence drilldowns with [inspectable aggregates](../030-inspectable-aggregates/_epic.md); no need to block investments on unrelated spending UI tasks.
- This epic covers investment visibility/performance, not deferred FI-10 benefits/tax/rewards/fee-advice scope. No tax filing, tax-lot optimization, trading, recommendations, retirement forecasting, automatic fund look-through, real-time quotes or guaranteed lifetime backfill. Detailed fee advice is deferred; supported fees still participate correctly in gain/returns.

## Delivery discipline

Each implementation slice has a test-first contract task and an independent verification task. Freeze literal financial expectations before implementation; record red/green commands, source commits, evidence and limitations in append-only task logs. Independent verification must be performed by someone other than the implementer when these tasks execute. Use synthetic/redacted fixtures, not committed personal holdings or credentials. Releases require API-level spending isolation and actual UI verification, not merely mocks or screenshots. This epic creation is documentation only: all tasks remain todo and unassigned; no provider access, schema migration, code change or deployment is claimed.

## Revision Log

- rev 1 (2026-11-10): Created from the investment research discussion and request for staged account visibility through returns, explicit spending separation, and possible replacement of Overview.

- rev 2 (2026-11-11): Owner authorized continuing through safe Schwab consent. Extract INV-00 spending isolation as an independent prerequisite to live consent, resolving the coverage/consent cycle. INV-01 coverage remains unverified; downstream ingestion milestones are unchanged.
