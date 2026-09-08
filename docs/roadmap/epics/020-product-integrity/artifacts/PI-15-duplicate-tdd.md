# PI-15 — Duplicate-accounting and lifecycle TDD contract

This artifact freezes the backend/API expectations for PI-04. It was authored
against the branch before duplicate-correction production code was added. The
tests use a six-row synthetic ledger in
`tests/duplicate_correction_fixture.py`; all expected values are declared by
the fixture and hand-calculated rather than obtained from application
analytics.

## Proposed API boundary

The tests use the resource name `/duplicate-corrections`, consistent with the
existing `/transfers` resource. PI-04 must provide:

- `POST /duplicate-corrections` with
  `canonical_transaction_id` and `duplicate_transaction_id`, returning HTTP
  200 and the created relationship with `id`, both endpoint IDs, and
  `status: "active"`;
- `GET /duplicate-corrections`, returning `{ "items": [...] }` including
  active and historical relationships; and
- `DELETE /duplicate-corrections/{id}`, deactivating (not deleting) a
  relationship and returning `{ "id": id, "status": "reversed" }`.

The transaction response must expose relationship state sufficiently for
ordinary Activity to retain both source rows and label them `canonical` and
`duplicate`. These names are a small API contract for the implementation and
UI handoff; they do not prescribe the database model.

## Hand-calculated fixture oracle

The fixture uses the ledger convention from PI-03: positive amounts are
expenses and negative amounts are income.

| Rows | Calculation | Expected |
|---|---|---:|
| Salary | `-100` | income `100` |
| Market A + Market B | `25 + 25` | expense `50` |
| Bookshop | `10` | expense `10` |
| Coffee A + Coffee B | `7 + 7` | expense `14` |
| All posted expenses | `25 + 25 + 10 + 7 + 7` | `74` |
| Net before correction | `100 - 74` | `26` |
| Active correction | exclude Market B `25` exactly once | expense `49` |
| Net after correction | `100 - 49` | `51` |

The two Coffee rows are deliberately identical-looking but have no explicit
relationship. They must remain counted. The selected Market rows are the only
rows that become a correction, with Market A canonical and Market B duplicate.

## Frozen cases

`tests/test_pi15_duplicate_tdd.py` covers:

1. active correction arithmetic across cashflow trend, monthly spend,
   category spend, Sankey, financial `is:spend` evidence, ordinary Activity
   search, relationship listing, and recurring-series input;
2. reversal of the relationship, restoration of both rows to accounting, and
   retention of historical relationship evidence;
3. rejection of same-row, pending, cross-account, unequal-amount,
   conflicting-currency, transfer-candidate, and refund-related selections,
   with no partially-created relationship;
4. rejection of a second correction that overlaps an active endpoint;
5. preservation of two identical-looking legitimate charges without an
   explicit action;
6. provider replay by the same identity leaving one row and the active
   correction unchanged;
7. material provider modification invalidating the correction and restoring
   normal accounting;
8. item removal invalidating the correction while retaining audit history; and
9. an unambiguous relink reapplying the correction from retained source
   evidence;
10. startup orphan cleanup invalidating history when an endpoint disappears; and
11. repeated application startup preserving one schema/history result without
    duplicate rows.

The provider lifecycle cases use the existing `SyncService` seam with local
fake clients; no provider credentials or live network calls are used.

## Initial red verification

Command:

```text
python -m pytest -q tests/test_pi15_duplicate_tdd.py
```

Initial result against the pre-PI-04 application:

```text
17 failed, 1 passed, 2 warnings in 1.70s
```

The failures are feature-red: the valid creation/reversal/lifecycle cases
receive `404 Not Found` because the duplicate-correction resource does not yet
exist; invalid-selection cases receive `404` instead of the required `400`.
There were no collection errors or malformed fixture failures. The one passing
case is the intentional conservative guard that identical-looking Coffee rows
remain counted without an explicit correction.

Control run:

```text
python -m pytest -q --ignore=tests/test_pi15_duplicate_tdd.py
230 passed, 3 warnings in 10.90s
```

The existing backend suite remains green; the only red tests are the newly
introduced PI-15 contract cases.

PI-04 must make these cases pass without changing their expected values or
weakening the no-automatic-hiding guard. A required test-contract change must
be escalated rather than edited in the implementation task.
