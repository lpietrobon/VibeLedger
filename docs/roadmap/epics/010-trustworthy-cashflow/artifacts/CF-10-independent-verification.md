# CF-10 independent accounting verification

## Scope and oracle

Verification was performed against integrated commit `fb6f7d1` (CF-09). The
verifier derives expected values from the posted event list, not from production
accounting functions or SQL views. It uses synthetic USD accounts representing
checking, credit card, payment account, partner, and investment counterparties.

## Reproducible command

```text
../VibeLedger/.venv/bin/python -m pytest -q tests/test_cf10_independent_verifier.py
```

Expected result on the accepted commit: `2 passed`.

## Evidence

| Scenario | Independently expected result | Observed |
|---|---:|---:|
| January posted cashflow | income 3,040; expenses 225; net 2,815 | pass |
| February posted cashflow | income 3,000; expenses -30; net 3,030 | pass |
| February category totals | sum is -30, including -120 refund category | pass |
| February paginated `is:spend` evidence | 3 rows, amount sum -30 | pass |
| Equal-size distinct third charge | January expense becomes 235 | pass |
| Pending 999 row | contributes zero | pass |
| Unconfirmed 75 transfer candidate | income 3,075; expense 45; net 3,030 | pass |
| Confirmed 75 internal pair | income 3,000; expense -30; net 3,030 | pass |

The wider suite also covers competing equal-amount matches, actual repeated
charges, replay idempotency, pending-to-posted replacement, invalid currencies,
sync retry atomicity, annotation persistence, source deletion, and re-detection
after rejection (`test_transfer_detector.py`, `test_sync_atomicity.py`,
`test_sync_and_annotations.py`, and `test_analytics_contracts.py`). Aggregate,
category, SQL-view, and paginated drill-down paths are checked against the same
CF-02 ledger in `test_cashflow_reporting.py`.

## Limits and disposition

An equal-amount unrelated row can remain an auto-detected *candidate* when only
amount/date/account evidence exists. It is not excluded from trusted totals until
confirmed, is visible for review, and rejection is remembered across detection.
This is therefore an explicit review limitation rather than a silent cashflow
misstatement. Currency conversion, incomplete provider history, and overlapping
duplicate account coverage remain explicitly qualified as unsupported.

No unresolved defect that silently changes scoped cashflow was found. CF-10 is
complete; any future improvement to candidate ranking belongs in a new task.
