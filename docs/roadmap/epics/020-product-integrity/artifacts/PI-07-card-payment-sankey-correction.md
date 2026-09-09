# PI-07 — card-payment Sankey correction

## Diagnosis addressed

PI-06 found no shared-accounting regression. Five real-looking linked
checking-to-credit-card repayments had exact opposite amounts and payment
evidence, but the card-side credit posted two to four days before the checking
outflow. The detector's generic rule required the outflow to post first, so the
rows remained unpaired and were conservatively counted. Three other payment
outflows had no covered counterpart in linked history and remain unpaired.

PI-19 froze this diagnosis using synthetic data. Its tests and artifact remain
unchanged.

## Implemented correction

The transfer detector now permits reverse posting order only when all of the
following hold:

- one side is a linked depository checking account and the other is a linked
  credit-card account;
- amounts are still nonzero, equal, and opposite;
- both rows carry payment evidence through the explicit effective category,
  provider credit-card-payment detail, or a payment/autopay description; and
- the reverse posting gap is no more than four elapsed days, matching the
  largest observed PI-06 shape.

The generic reverse-order collision guard remains in force for all other
account-role/evidence combinations. Forward-order matching still uses the
caller-provided detector window. Candidate ranking uses absolute elapsed days so
forward and approved reverse candidates are compared by the same proximity
measure.

Manual pairing and candidate confirmation use the same validation boundary. A
reverse-order card-payment candidate is therefore still an unconfirmed,
counted candidate until the user confirms it. Once confirmed, the existing
shared accounting predicate excludes both rows from income/spending and Sankey;
the underlying card purchase remains counted once. No category-name suppression
or automatic confirmation was added.

The Transfer Detection page now states that detection requires both posted sides
in linked-account history and that unmatched payments remain counted. This is a
coverage qualification, not a claim that a missing counterpart is a transfer.

## Verification

Synthetic focused checks:

```text
uv run --extra dev pytest -q \
  tests/test_pi19_card_payment_tdd.py \
  tests/test_pi07_card_payment_detection.py \
  tests/test_transfer_detector.py \
  tests/test_transfers_api.py
31 passed, 2 warnings
```

The frozen PI-19 suite passes unchanged. The new PI-07 tests cover the observed
four-day reverse case, reject a fifth-day reverse case, and reject a reverse
same-amount pair without payment evidence.

`git diff --check` and Python compilation pass. Full backend, frontend, typecheck,
build, roadmap scan, and final diff verification are recorded in the task log
when the implementation commit is finalized.

## Scope decision

This is a transfer-detection/review correction plus history-coverage
communication. No accounting policy change, Sankey-specific suppression, live
ledger mutation, or PI-19 contract change was needed. No escalation is required.
