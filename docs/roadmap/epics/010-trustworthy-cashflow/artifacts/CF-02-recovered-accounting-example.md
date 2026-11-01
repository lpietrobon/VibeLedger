# Recovered accounting example — partial CF-02 output

This example is already encoded in the unpublished draft's
`tests/test_accounting_integrity.py::test_posted_ledger_matches_every_chart_and_drilldown_before_and_after_confirmation`.
The fresh draft test run passes it. The arithmetic below can be checked by hand;
it is not a complete decision table or independent verifier sign-off.

All rows are dated March 5, 2024; the reporting clock is March 15, 2024. Amounts
below describe cash direction in plain language; the provider uses positive
amounts for outgoing money. The three accounts are synthetically linked accounts.

| Event | Account | Amount | Initial treatment |
|---|---|---:|---|
| Salary | Checking | 2,000 incoming | Income |
| Dinner | Credit card | 120 outgoing | Expense |
| Card repayment | Checking | 200 outgoing | Unconfirmed candidate: counted expense |
| Card repayment counterpart | Credit card | 200 incoming | Unconfirmed candidate: counted income |
| Payment-account funding | Checking | 75 outgoing | Confirmed internal transfer: excluded |
| Funding counterpart | Payment account | 75 incoming | Confirmed internal transfer: excluded |
| Payment-account purchase | Payment account | 25 outgoing | Expense |
| Confirmed merchant refund | Credit card | 40 incoming | Reduces expenses |
| Pending dinner | Credit card | 999 outgoing | Excluded from realized totals |
| Pending income | Checking | 500 incoming | Excluded from realized totals |

Before the card repayment is confirmed: income = 2,000 + 200 = **2,200**;
expense = 120 + 200 + 25 - 40 = **305**; net = **1,895**.

After confirmation: income = **2,000**; expense = 120 + 25 - 40 = **105**;
net remains **1,895**. The uncertain pair initially inflates gross flows; review
resolves that uncertainty. The refund reduces expense rather than becoming earned
income. Payment funding and the pending transactions never add realized spending.

The test compares multiple aggregate endpoints, the effective SQL view, and the
spending drill-down against explicit expected values. Other draft tests cover
period boundaries, linked refund categories, and refund-only buckets. CF-02 still
needs a complete decision table, cross-period worked totals, history/coverage
semantics, partner/investment counterpart cases, and uncertain reimbursement
treatment. The account's synthetic name does not demonstrate provider support.
