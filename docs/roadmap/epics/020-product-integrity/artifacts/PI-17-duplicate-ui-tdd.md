# PI-17 — Duplicate-correction UI/API-client TDD contract

This artifact freezes the client and interaction expectations for PI-05. It is
deliberately red against the current frontend: no duplicate-correction client
methods or UI workflow exists yet. PI-05 may make product-code changes to pass
these tests, but may not change their labels, payloads, or fixture oracle
without escalation.

## Literal client contract

The API client must expose these operations:

| Operation | Request | Required result |
|---|---|---|
| List relationships | `GET /duplicate-corrections` | Preserve relationship `id`, endpoint IDs, and `status` so Activity can label rows and find a reversal target. |
| Create correction | `POST /duplicate-corrections` with JSON `{ "canonical_transaction_id": 102, "duplicate_transaction_id": 101 }` | Send the explicit IDs selected by the user; do not persist a local-only selection. |
| Reverse correction | `DELETE /duplicate-corrections/9001` with no request body | Deactivate the durable relationship and return its reversed status. |

The client-facing method names frozen by the tests are
`getDuplicateCorrections`, `createDuplicateCorrection`, and
`reverseDuplicateCorrection`. The create method accepts camelCase client
arguments and maps them to the literal snake_case wire payload above.

## Interaction fixture and labels

The deterministic fixture uses four posted USD transactions in one account:

| ID | Description | Amount | Initial state |
|---:|---|---:|---|
| 101 | MARKET A | 25 | ordinary |
| 102 | MARKET B | 25 | ordinary |
| 103 | COFFEE A | 25 | ordinary legitimate charge |
| 104 | COFFEE B | 25 | ordinary legitimate charge |

The market rows are the explicit pair. The coffee rows are intentionally
similar-looking but have no relationship and must never acquire one merely
because their date, amount, or description resembles another row.

The visible labels are fixed as follows:

- action: **Mark as duplicates**;
- canonical-choice heading: **Choose the canonical transaction**;
- canonical row label: **Canonical**;
- duplicate row label: **Marked duplicate**;
- reversal action: **Reverse duplicate correction**;
- reversal confirmation: **Both records will again count normally.**;
- invalid-selection feedback: **Select exactly two transactions to mark as duplicates.**;
- creation confirmation: **Confirm duplicate correction**; and
- reversal confirmation action: **Reverse correction**.

The creation confirmation must also display this exact warning:

> Both imported records will remain visible. Only the record marked duplicate
> will be excluded from spending and income totals.

## Frozen interaction cases

`frontend/src/routes/duplicate-correction-tdd.test.tsx` covers:

1. Desktop selects exactly two rows, opens the confirmation with the literal
   warning, chooses either row as canonical, and confirms through the API
   client. The test uses keyboard Enter to activate the action and checks the
   exact create payload for the selected canonical/duplicate IDs.
2. Mobile selects exactly two rows and can activate the same action by
   keyboard, reaching the same duplicate-correction dialog.
3. One selected row and three selected rows receive deterministic feedback and
   cannot submit a correction.
4. An active relationship renders both **Canonical** and **Marked duplicate**
   labels. Opening a row exposes **Reverse duplicate correction**, requires the
   literal reversal confirmation, calls the durable DELETE operation with ID
   `9001`, and invalidates the ledger cache after both create and reverse.
5. The two un-related coffee rows remain unlabeled and no create operation is
   inferred or issued for them.

`frontend/src/lib/api/duplicate-correction-tdd.test.ts` separately captures the
literal GET/POST/DELETE requests so route tests cannot pass by mocking only a
local selection state.

## Initial red result

Command:

```text
cd frontend && npm test -- --run src/lib/api/duplicate-correction-tdd.test.ts src/routes/duplicate-correction-tdd.test.tsx
```

Initial result against the pre-PI-05 frontend:

```text
7 failed, 1 passed
```

The API-client cases fail because the three frozen client methods are not yet
implemented. The route cases fail because TransactionsPage currently exposes
only annotation editing, has no duplicate action/dialog/relationship labels,
and has no duplicate-cache workflow. The similar-charge guard is intentionally
asserted as a safety invariant and passed independently; it must remain green
after PI-05 implementation.
