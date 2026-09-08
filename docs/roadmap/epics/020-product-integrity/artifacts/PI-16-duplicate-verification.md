# PI-16 — Independent duplicate-accounting verification

## Scope and immutable contract

The PI-15 fixture and `tests/test_pi15_duplicate_tdd.py` were run without any
edits. Their oracle is literal: income `100`, expense `74`, and net `26` before
correction; after marking Market A canonical and Market B duplicate, income is
`100`, expense is `49`, and net is `51`. The contributing expense IDs change
from Market A, Market B, Book, Coffee A, Coffee B to Market A, Book, Coffee A,
Coffee B. Reversal restores the original set and totals. The two Coffee rows
remain counted because they have no explicit relationship.

## Independent audit

The frozen suite checks the shared accounting paths (cashflow trend, monthly
spend, category spend, Sankey, recurring detection, `is:spend` search), source
visibility and relationship labels, reversal, eligibility rejection,
provider replay, material modification, item removal, unambiguous relink,
orphan cleanup, and idempotent startup schema/history. These results were
independently inspected against the shared `posted_activity` predicate and the
`effective_transactions` view. All financial aggregate consumers found in the
API use that predicate or the view; ordinary Activity intentionally remains a
source-evidence query and therefore retains both rows.

The audit also challenged the lifecycle and detector boundaries directly:

- Same-account provider/account currency conflicts are ineligible.
- Account currency changes and provider transaction currency changes invalidate
  an active correction before the changed source can remain excluded.
- An active duplicate endpoint is not offered to later transfer or refund
  detection as a candidate or counterparty.
- Reversal and two legitimate same-value charges remain covered by PI-15.
- Provider replay, source removal, startup orphan cleanup, and unambiguous
  relink remain covered by PI-15; no implicit reattachment was introduced.

## Code-only repairs made during verification

PI-16 found and repaired three implementation gaps without changing PI-03,
PI-15's fixture, or PI-15's tests:

1. Duplicate currency validation now rejects provider/account currency
   conflicts and unofficial currency evidence rather than accepting a value
   that the reporting layer cannot safely aggregate.
2. Account-currency changes and provider transaction-currency changes now
   invalidate active corrections, restoring normal accounting until review.
3. Transfer and refund detectors skip active duplicate endpoints, so a later
   matching row cannot create a new relationship around a record the user has
   already declared duplicate.

The independent adversarial cases live in
`tests/test_pi16_duplicate_verifier.py`; they do not alter the frozen contract.

## Verification commands and results

- `python -m pytest -q tests/test_pi15_duplicate_tdd.py` — **18 passed**, 2 warnings.
- `python -m pytest -q tests/test_pi16_duplicate_verifier.py tests/test_pi15_duplicate_tdd.py` — **22 passed**, 2 warnings.
- `python -m pytest -q tests/test_pi15_duplicate_tdd.py tests/test_transfer_detector.py tests/test_refund_detector.py` — **35 passed**, 2 warnings.
- `python -m pytest -q` — **252 passed**, 3 warnings.
- `python -m py_compile app/services/duplicate_corrections.py app/services/sync_service.py app/services/transfer_detector.py app/services/refund_detector.py tests/test_pi16_duplicate_verifier.py` — passed.
- `git diff --check` — passed.
- `python docs/roadmap/scan.py` — 3 epics, 44 tasks, 0 issues.
- Frontend checks were not available in this checkout because `frontend/node_modules` is absent; attempting the npm check was blocked by the environment's package/network approval boundary. No frontend files were changed.

## Verdict

**PASS.** PI-04 satisfies the immutable PI-15 accounting/lifecycle contract,
with the code-only repairs above included in the verification commit. No PI-15
test or fixture change was required, and no UI task was touched.
