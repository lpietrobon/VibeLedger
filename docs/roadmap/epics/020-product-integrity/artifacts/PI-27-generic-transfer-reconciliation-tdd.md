# PI-27 — generic transfer reconciliation TDD contract

## Decision

VibeLedger resolves an internal movement automatically only when the evidence is
both exact and unambiguous. The rule applies to every pair of linked accounts;
account type and institution are signals, not a boundary definition or allowlist.

The accepted first release is intentionally one-to-one and same-currency. Fees,
foreign exchange, split payments, aggregations, pending rows, duplicates, absent
counterparts, and competing equal-quality matches abstain rather than being
approximated.

## Frozen examples

`tests/test_pi27_generic_transfer_reconciliation_tdd.py` uses synthetic posted
USD transactions only. It asserts automatic confirmation for four exact,
mutually-unique, two-sided structured-evidence shapes:

| Route | Amount | Dates | Evidence |
|---|---:|---|---|
| Checking → savings in the same institution | 101 | Jan 10 → Jan 11 | `TRANSFER_OUT` / `TRANSFER_IN` |
| Checking → checking at another institution | 102 | Jan 12 → Jan 14 | `TRANSFER_OUT` / `TRANSFER_IN` |
| Checking → linked wallet | 103 | Jan 15 | `TRANSFER_OUT` / `TRANSFER_IN` |
| Checking → linked card repayment | 104 | Card receipt Jan 18; outflow Jan 20 | two card-payment details |

It additionally pins a future exact route after a person has already confirmed
the same ordered account-pair plus normalized two-sided description signature.
That route is evidence, not a broad “all movements between these accounts” rule.

The collision fixture proves that a rent outflow and one card-side “Payment
received” row sharing amount/date remain an **unconfirmed candidate**, while a
structured-evidence tie remains unpaired. The lifecycle fixture proves that
rejection prevents redetection and that an automatically confirmed relationship
is removed when a later provider modification breaks equal amounts.

## Baseline

Before PI-28, run at local commit `a6e51eb`:

```text
uv run --extra dev pytest -q tests/test_pi27_generic_transfer_reconciliation_tdd.py
3 failed, 1 passed
```

The failures are deliberate: generic structured matches and a known manual route
are still created as candidates, and auto-confirmation lifecycle revalidation is
not implemented. The collision control already passes because it is not silently
confirmed.

## Change control

PI-28 and PI-29 may add production code and separate tests, but they may not edit
this file's test module or revise the cases above. Any required change is a
product-contract escalation.
