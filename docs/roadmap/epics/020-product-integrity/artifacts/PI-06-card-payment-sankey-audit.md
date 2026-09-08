# PI-06 — card-payment Sankey audit

## Question and evidence boundary

The report that a Sankey contains a category such as “Credit card payments” is
not, by itself, evidence of double-counting. The category name can come from
provider classification, a rule, or a manual category; it says nothing about
whether a matching linked-account transfer was confirmed.

This audit was performed against local integrated commit `2010806` (the same
product tree published after PI-18). This checkout contains no user database or
deployment target—only `.env.example`—so it cannot truthfully name or classify
the rows that produced the observed chart. No private transaction data was
copied into the repository. The conclusion below is therefore about the current
accounting path and the precise, safe procedure required to classify the observed
period; it is **not** a declaration that the observed production-like rows are
already explained.

## Confirmed implementation facts

| State of a posted row | Current shared accounting result | Sankey result |
| --- | --- | --- |
| Confirmed `TransferPair` on either linked account | excluded by `posted_activity(..., include_transfers=False)` / `exclude_confirmed_transfers()` | no category contribution |
| Unconfirmed `TransferPair` candidate | deliberately retained | outgoing payment can appear in its effective category; incoming side remains normal income unless refund evidence applies |
| No recorded pair | deliberately retained | outgoing payment can appear in its effective category |
| Pending row | excluded | no contribution |
| Active manual duplicate | duplicate side excluded | no contribution from that side |

`analytics_cashflow_sankey()` in `app/api/routes.py` uses the shared
`posted_activity(..., include_transfers=False)` scope and `expense_amount()`;
it does not have a Sankey-only category rule. `effective_transactions` uses the
same confirmed-transfer exclusion. Consequently, a row that is both confirmed
and contributing to a Sankey expense category would be a shared-accounting
regression, not a chart-label issue.

The CF-02 synthetic ledger includes a linked checking-to-credit-card repayment
of 120 alongside a distinct card purchase of 120. Its January oracle is income
3,040, expense 225, net 2,815: the repayment contributes zero while the purchase
is counted once. The current code path therefore satisfies the required baseline
in the hand-checkable fixture. The existing suite had not yet named that
repayment directly in the Sankey payload; PI-19 must retain that literal baseline
while adding the observed path.

## Safe operator workflow for the observed period

Run these steps only in the deployed/local environment containing the ledger;
keep the output local. Do not paste raw names, merchant strings, account masks,
or transaction IDs into roadmap artifacts or tests.

1. Record the exact Insights start and end dates and save the local response from
   `GET /analytics/cashflow-sankey?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`.
   Identify the exact effective category shown by the UI, not merely a remembered
   display phrase.
2. Use the same bounds and category in Activity. Inspect all pages and retain a
   private working table containing only the minimum evidence: date, signed
   amount, account role, effective category, pending state, transfer-pair ID and
   confirmation state, and whether a counterpart is present in the linked-account
   history.
3. Classify each contributing outgoing row as follows:
   - **confirmed transfer:** a `TransferPair.confirmed = true` includes the row;
     if it nevertheless contributes, capture this as the shared-path regression;
   - **unconfirmed candidate:** a pair includes the row with `confirmed = false`;
     it is intentionally counted until review/confirmation;
   - **undetected / missing counterpart-history:** no pair exists. Establish
     whether an opposite linked-account row is present in available history. If
     absent, call it missing history; if present but unpaired, call it undetected.
     Do not infer either from equal amounts or category text alone.
4. Confirm a known true candidate through the existing Transfer Detection review
   flow, then repeat the identical Sankey and Activity queries. It must disappear
   from the outgoing expense category while its original credit-card purchases
   remain. If no counterpart/history exists, do not confirm or hide it merely to
   improve the chart.

A private read-only SQL inspection can support step 3. It intentionally requires
the operator to provide the date range and effective category locally:

```sql
SELECT
  et.date,
  et.amount,
  et.effective_category,
  et.pending,
  p.id AS transfer_pair_id,
  p.confirmed AS transfer_confirmed,
  CASE
    WHEN p.confirmed = 1 THEN 'confirmed transfer'
    WHEN p.id IS NOT NULL THEN 'unconfirmed candidate'
    ELSE 'unpaired: determine undetected vs missing history'
  END AS classification,
  et.expense_amount
FROM effective_transactions et
LEFT JOIN transfer_pairs p ON et.id IN (p.txn_out_id, p.txn_in_id)
WHERE et.date BETWEEN :start_date AND :end_date
  AND et.effective_category = :effective_category
ORDER BY et.date, et.id;
```

The query is evidence only. It must not be used to bulk-confirm, recategorize, or
hide rows.

## Decision for child work

The accounting invariant is already unambiguous:

- correctly confirmed checking-to-linked-credit-card repayments are excluded from
  income, spending, and Sankey categories;
- unresolved candidates and unpaired rows remain counted conservatively;
- the remedy must target the discovered state, never suppress a category by name.

PI-19 is now ready to freeze a failing regression only after the safe workflow
provides one concrete observed classification. Its required fixture has two
non-negotiable cases: the confirmed 120 repayment baseline (zero Sankey
contribution) and the observed state with its intentional result. PI-07 remains
bounded to that outcome: shared-accounting repair for a confirmed regression, or
a transfer-review/history-coverage workflow repair for unresolved evidence.

PI-09 is also unblocked: its design exploration may rely on the invariant above
but must not assume the chart category is an accounting defect.

## Verification

At commit `2010806`:

```text
python -m pytest -q \
  tests/test_cashflow_reporting.py::test_cf02_oracle_api_sql_categories_and_all_evidence_pages \
  tests/test_cf10_independent_verifier.py \
  tests/test_analytics_contracts.py::test_posted_analytics_and_spend_drilldown_share_the_same_rows \
  tests/test_transfer_detector.py::test_unrelated_equal_amounts_still_pair_accepted_limitation \
  tests/test_insights_analytics.py
18 passed
```

This covers the hand-calculated linked-card fixture, conservative unresolved
candidates, shared Activity evidence, transfer-detector limits, and the Sankey
endpoint. It does not substitute for the private-row classification workflow.

