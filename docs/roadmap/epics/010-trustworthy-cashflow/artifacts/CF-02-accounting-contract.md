# CF-02 — cashflow reporting contract

Accepted intent: [spirit](../spirit.md). Scope evidence: [CF-01 audit](CF-01-audit.md).
This specifies outcomes; the existing implementation and unpublished draft must
be checked against it. No bookkeeping engine, connector, FX system, or agent layer
is required. The examples use USD and synthetic accounts.

## Boundary, identity, and posting

All linked accounts form one boundary, independent of owner or account type.
Checking, credit cards, payment accounts, a partner's linked account, and a linked
investment account can be transfer counterparties. Holdings-only data cannot prove
a transaction match. Income/expense here are reporting classifications, not tax
categories or changes in net worth.

Count realized activity on its provider **posting date**, not authorization or
import date. Exclude pending rows from realized totals while keeping them
inspectable. When a provider explicitly replaces a pending record, count the
posted replacement once and preserve applicable manual decisions. Use inclusive
date ranges. Replaying the same provider identity adds nothing; two different
provider identities with identical descriptions/date/amount are two records until
stronger evidence establishes an import duplication. A suspected double charge
remains a real recorded outflow while under review.

## Decision table

Amounts are described positively below. Provider storage uses positive for an
outflow and negative for a receipt. Net cashflow = reported income - net expenses.

| Posted event / state | Income effect | Expense effect | Evidence / review |
|---|---:|---:|---|
| External salary or other receipt | +amount | 0 | Category explains source; not necessarily earned/taxable income |
| External purchase, fee, gift, or payment | 0 | +amount | Includes boundary-crossing transfers while no linked counterpart is established |
| Credit-card purchase | 0 | +amount | Purchase posting date; payment of the linked card is a separate internal movement |
| Confirmed valid linked-account transfer, including card repayment or payment-account funding | 0 | 0 | Both posted sides, opposite equal amounts, different linked accounts, compatible known currency; retain both evidence rows |
| Unconfirmed or ambiguous transfer candidate | Normal receipt/refund treatment | Normal outflow/refund treatment | Reviewable and included; candidate status alone cannot suppress either row |
| One-sided legacy transfer override | Normal receipt treatment | Normal outflow treatment | Inert for exclusion; a label alone cannot remove money |
| Confirmed refund, or existing high-confidence likely refund with unique purchase evidence | 0 | -amount | Retain reason and link where available; manual refund/not-refund choice wins |
| Unclassified incoming person-to-person reimbursement | +amount | 0 | Keep original gross spending; do not silently match to a purchase or require routine manual linking |
| Suspected actual repeated charge | 0 | +amount per recorded charge | Flag if existing evidence supports it; dismissing a warning does not delete or exclude a charge |
| Replayed identical provider record | No additional effect | No additional effect | Import identity, not amount similarity |
| Pending / future-posted activity outside selected dates | 0 | 0 | Inspect separately; enters the correct period if/when posted |

Retain the existing high-confidence refund distinction: an exact unique eligible
same-account/amount/name purchase match may be `likely`; a provider refund code
or explicit user choice may be `confirmed`. Unknown/ambiguous matches are not
automatically refunds. A likely refund remains explainable and correctable;
`not_refund` restores normal incoming treatment. A confirmed transfer takes
precedence over a refund classification while paired; unpairing must reevaluate
the refund evidence. Do not count one purchase as evidence for multiple automatic
refunds. Installments, partial/grouped reimbursements, and reward optimization
are outside this hardening scope.

An unconfirmed transfer candidate does not override independent refund evidence:
its incoming row reduces expense if it qualifies as a refund; otherwise it is
income. Candidate status changes neither row's normal classification. The worked
repayment/funding candidates below have no refund evidence and therefore count
as ordinary income and expense until confirmed.

## Categories and drill-down evidence

Use the current manageable vocabulary, including uncategorized; no category tree
redesign. First applicable effective category: explicit user category on this
row; otherwise a valid matched refund's original purchase effective category;
otherwise the enabled rule result (rank then ID); otherwise mapped provider
detailed/primary category; otherwise uncategorized. A rule change must update
its stored result through the existing recomputation path. A refund without an
eligible purchase link uses its own ordinary category fallback. User decisions
survive routine sync; clearing an override restores inherited classification.

A refund posted in February for a January purchase reduces **February** expense
in the purchase's category, including when that category becomes negative. It
does not erase the January purchase or become February earned income. A later
category correction to the purchase propagates to a linked refund unless the
refund has its own user override. Reclassification changes categories, not the
total. Charts must preserve negative categories or use an honest simpler display.

Every amount/count has a server-queryable contributing set using the same period,
categories, posted state, and transfer/refund policy, including all pages. A review
decision refreshes both the total and the evidence. Optional agents query those
existing functions/APIs, not a second money calculation over exported transactions.

## Comparisons and incomplete coverage

- Current monthly/yearly range ends at the reporting date, not the latest row.
  Default monthly comparison is month-to-date versus the same calendar day last
  month, clipped to that month's last day. When the current month is complete,
  compare the two complete months. Here complete means the reporting date is the
  calendar month's last day; it does not assert complete provider coverage.
  Year-to-date compares through the same month/day
  last year, clipping February 29 to February 28 when needed.
- Examples: March 15 compares with February 1–15; March 31 compares with all
  February; February 28, 2025 compares with all January; January 2 compares with
  December 1–2 of the previous year. February 29, 2024 YTD compares with January
  1–February 28, 2023. Explicit historical period views show their actual bounds.
- Absolute change = current expense - prior expense. Percentage change uses
  `change / abs(prior) * 100`; show no percentage when prior is zero. Negative
  expenses from refunds remain negative. Label partial periods and any projection
  explicitly; a projection is not observed spend.
- Missing history is **unknown coverage**, not verified zero expenditure. With
  no stored completeness evidence, present recorded activity and an unverified-
  coverage qualification; do not imply a sync timestamp proves all history exists.
  No prior rows means no reliable baseline, not a confident improvement. A
  successful zero-row sync can still leave coverage unknown.
- Mixed currencies have no meaningful combined nominal amount. Refuse that
  combined view or qualify its unsupported state prominently rather than label it
  a trustworthy dollar total. Unknown currency is unverified, not inferred USD.
  Conversions are out of scope. The same rule applies to overlapping duplicate
  account coverage until explicitly resolved through existing account management.

## Hand-calculated example

[Machine-readable rows and fixed expected results](CF-02-ledger-fixture.json)
cover linked checking, credit card, payment account, partner checking, and an
investment account used only as a transfer counterparty.

January 2024 income: salary **3,000** + unclassified reimbursement **40** =
**3,040**. Expenses: card purchase **120** + payment-account purchase **35** + two
distinct coffee charges **10 + 10** + external gift **50** = **225**. Net **2,815**.
Paired card repayment **120**, payment funding **80**, partner transfer **200**,
and investment transfer **100** each contribute zero on both sides. Pending
purchase **999** contributes zero. The full original purchase remains spending
despite the unlinked reimbursement.

February 2024 income: salary **3,000**. Expenses: a purchase posted February 1
(authorized January 31) **80** + fee **10** - the January purchase's refund **120**
= **-30**. Net **3,030**. The January purchase category has a February **-120**
balance; other February categories total **90**.

Year-to-date through February 29: income **6,040**, expenses **195**, net **5,845**.
These values are explicit arithmetic, not generated by production analytics.
Monthly expense movement is **-255** and **-113.33%** from January to February;
the negative February expense is a refund effect, not a rendering error.

## Changes to the evidence

| Change to the fixture | Expected result |
|---|---|
| Replay any existing provider ID | No totals/count increase |
| Third genuinely distinct January coffee charge of 10 | January expense 235, net 2,805; do not hide it based on same amount |
| Add unresolved February funding pair of 75 | February income 3,075, expense 45, net still 3,030; confirm pair restores 3,000 / -30 |
| Reject that candidate | Same counted income/expense; don't recreate it automatically without a legitimate evidence/user change |
| Correct January purchase posting date to February 1 | January expense 105; February expense 90; YTD expense remains 195; refund still posted February |
| Newly link the account receiving January's gift of 50, and establish the counterpart | January expense becomes 175; receipt is internal, not extra income; YTD expense 145. Historical boundary improves with newly linked evidence |
| Pending 999 becomes a posted 45 purchase on March 1 | January/February unchanged; March expense +45, one surviving posted record |
| Change January purchase category | January category allocation and linked February refund category move together; monthly totals unchanged |

Linking a new account can add genuinely external transactions as well as reveal
internal pairs; recompute past totals rather than freeze snapshots. If a provider
corrects/deletes a paired source row, invalidate stale reconciliation and recompute
the remaining evidence. Manual confirmations do not justify retaining an invalid
pair. Missing counterpart rows remain counted/uncertain until established.

## Decisions and implementation scope

The user's boundary, posting-date, recomputation, and gross-reimbursement choices
resolve the material product questions. Comparison edge cases and category
precedence above make those choices executable while preserving existing refund
behavior. Unsupported provider/history/currency/account-identity cases require
honest limits, not guessed facts. No new product decision is needed to begin the
test and correctness tasks; any proposed expansion must get a new scope decision.
