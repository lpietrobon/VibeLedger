# PI-18 — Independent duplicate-correction UI verification

## Scope and immutable inputs

Verification was performed against integrated PI-05 implementation commit
`9fd95c3`. PI-03, PI-15, PI-16, and PI-17 were read before testing. PI-17's
tests, fixture, labels, payloads, and artifact were not edited.

The accounting oracle remains PI-16's independently checked PI-15 fixture:
income `100`, expense `74`, and net `26` before correction; income `100`,
expense `49`, and net `51` when the duplicate expense is excluded; and the
original `74`/`26` result after reversal. The two unrelated same-value Coffee
rows remain included.

## Independent checks

The unchanged frozen suite exercised the shared fixture through both responsive
layout paths:

- Desktop table: selecting exactly two rows, keyboard activation, canonical
  choice, literal POST IDs, and successful refresh.
- Mobile rows: selecting exactly two rows, keyboard activation, relationship
  dialog, labels, reversal, literal DELETE ID, and successful refresh.
- Both paths: one/three-row validation and the no-automatic-inference guard for
  similar-looking legitimate charges.

The resulting source evidence remains inspectable: both rows are visible,
canonical/marked-duplicate labels are shown, transaction detail shows the
relationship and related-record navigation, and reversal is available from
detail with its explicit confirmation. The workflow uses the durable API
relationship and invalidates the shared ledger cache after successful create and
reverse, so downstream projections can refetch the corrected accounting state.

The distinct PI-18 test additionally rejects both mutation promises. It checks
that create and reverse failures display the server error, leave the relevant
dialog open for recovery, and do not report a successful cache invalidation.
This covers error handling without weakening the frozen success contract.

## Verification commands and results

- `cd frontend && npm test -- --run src/lib/api/duplicate-correction-tdd.test.ts src/routes/duplicate-correction-tdd.test.tsx` — **8 passed** unchanged.
- `cd frontend && npm test -- --run src/lib/api/duplicate-correction-tdd.test.ts src/routes/duplicate-correction-tdd.test.tsx src/routes/duplicate-correction-verifier.test.tsx` — **10 passed**.
- `cd frontend && npm test -- --run` — **54 passed** across 9 files.
- `cd frontend && npm run typecheck` — passed.
- `cd frontend && npm run build` — passed.
- `python -m pytest -q tests/test_pi15_duplicate_tdd.py tests/test_pi16_duplicate_verifier.py` — **22 passed**, 2 warnings.
- `git diff --check` — passed.
- `python docs/roadmap/scan.py` — 3 epics, 44 tasks, 0 issues.

## Code changes and verdict

No production code repair was necessary. The only added code is the distinct
adversarial test `frontend/src/routes/duplicate-correction-verifier.test.tsx`.
No frozen TDD contract required escalation. **PASS.**
