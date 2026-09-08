# PI-05 — Duplicate correction UI walkthrough

This walkthrough exercises the PI-17 fixture through the implemented React
Activity workflow. It is product evidence for PI-05; the immutable interaction
contract remains in [PI-17](PI-17-duplicate-ui-tdd.md).

## Synthetic fixture

The Activity response contains four posted USD rows in one account:

| ID | Description | Amount | Initial state |
|---:|---|---:|---|
| 101 | MARKET A | 25 | ordinary |
| 102 | MARKET B | 25 | ordinary |
| 103 | COFFEE A | 25 | ordinary |
| 104 | COFFEE B | 25 | ordinary |

The Market rows are the pair the user explicitly corrects. The Coffee rows are
separate legitimate charges and receive no state merely because they look alike.

## Walkthrough result

1. On the desktop table, selecting rows 101 and 102 exposes **Mark as
   duplicates**. The same action is available from the mobile row layout.
2. Activating the action with Enter opens **Confirm duplicate correction**, whose
   heading is **Choose the canonical transaction**. Both selected rows are shown
   with date, account, and amount, and the canonical radio choice is explicit.
3. The confirmation warning states that both imported records remain visible and
   only the marked duplicate is excluded from spending and income totals.
4. Choosing 102 as canonical and confirming sends
   `{canonical_transaction_id: 102, duplicate_transaction_id: 101}` through the
   API client, clears the selection, shows success feedback, and invalidates the
   ledger cache.
5. Reloading Activity with the active correction shows **Canonical** on 102 and
   **Marked duplicate** on 101 in both mobile and desktop presentations. Opening
   either row shows the structured relationship and a **View related transaction**
   affordance; opening the related row works from that detail context.
6. Choosing **Reverse duplicate correction** opens the explicit confirmation
   **Both records will again count normally.** Confirming sends DELETE for
   correction 9001, shows success feedback, and invalidates the ledger cache.
7. Selecting one or three rows leaves the action disabled and shows
   **Select exactly two transactions to mark as duplicates.** No relationship is
   inferred for the two Coffee rows.

## Verification evidence

- `cd frontend && npm test -- --run src/lib/api/duplicate-correction-tdd.test.ts src/routes/duplicate-correction-tdd.test.tsx` — **8 passed**.
- `cd frontend && npm test -- --run` — **52 passed**.
- `cd frontend && npm run typecheck` — passed.
- `cd frontend && npm run build` — passed.
- `python -m pytest -q tests/test_pi15_duplicate_tdd.py tests/test_pi16_duplicate_verifier.py` — **22 passed**.

The API-client and route tests use the same four-row fixture and immutable labels,
payloads, and lifecycle effects frozen by PI-17. No PI-17 test or expected value
was changed.
