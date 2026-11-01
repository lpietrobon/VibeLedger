# PI-19 — card-payment Sankey TDD contract

## Privacy boundary

This artifact uses synthetic dates, amounts, labels, and identifiers only. It
records the shape of the PI-06 finding, not any live ledger values.

## Audited baseline

The test was authored against commit `29a47c1` on branch
`roadmap/product-integrity-inspectability`. The focused red command was:

```text
.venv/bin/pytest -q tests/test_pi19_card_payment_tdd.py
```

Result at the audited baseline:

```text
2 failed, 1 passed
```

The two failures are intentional TDD contracts: detection and review reject a
card-payment repayment when the card-side credit posts before the checking-side
outflow. The passing test protects the coverage boundary: without a covered
counterpart, the system must not invent a transfer and must keep the payment
counted.

## Fixture rationale

The fixture creates active linked checking and credit-card accounts, a synthetic
card purchase, and a matching card-payment repayment. The card credit is posted
before the checking outflow, while both payment rows have explicit payment
evidence and equal opposite amounts. A separate checking payment has no covered
counterpart. A generic reverse-order equal-amount collision remains covered by
the existing rejection test.

## Frozen contract

`tests/test_pi19_card_payment_tdd.py` must pass after the implementation is
repaired, without weakening the generic collision guard:

1. The evidence-qualified reverse-order repayment creates exactly one
   unconfirmed transfer candidate; both payment rows are exposed as candidates
   and remain counted until confirmation.
2. The candidate can be reviewed and confirmed. After confirmation, both
   repayment rows contribute zero income, zero spending, and no Sankey expense
   category; the synthetic purchase remains counted once.
3. A payment with no covered counterpart remains unpaired and counted, and
   reporting communicates that linked history is unverified.

No category-name suppression is an acceptable implementation of this contract.

## Execution log

- 2026-09-09: Added the synthetic regression suite; no production code or live
  ledger was changed.
- 2026-09-09: Focused suite is intentionally red at the audited baseline:
  `2 failed, 1 passed`.
