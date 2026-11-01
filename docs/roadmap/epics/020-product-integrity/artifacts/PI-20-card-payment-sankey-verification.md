# PI-20 — card-payment Sankey correction verification

## Scope and evidence boundary

This independent verification evaluated the PI-07 implementation at commit
`2c45f7d` on branch `roadmap/product-integrity-inspectability`; the production
change under review is `140a7c3`. PI-19, PI-06, and CF-02 were treated as
immutable contracts/evidence. All newly added fixture values are synthetic.
No live ledger data was read or changed.

## Verification verdict

**PASS.** PI-07 fixes the diagnosed reverse-posting-order detection gap without
weakening the accounting contract or the generic collision guard. A qualifying
checking-to-credit-card repayment becomes one unconfirmed candidate, remains
counted until a user confirms it, and then both repayment rows are excluded from
income, spending, and Sankey while the card purchase remains counted once.

No production-code repair was necessary during PI-20.

## Independent checks

The separate verifier suite in `tests/test_pi20_card_payment_verifier.py`
confirmed:

- payment evidence is required on both legs of the reverse-order exception;
- the exception is restricted to a checking outflow and credit-card receipt;
- two equally close qualified card receipts remain unpaired rather than being
  resolved by row ordering;
- ordinary forward matching still obeys the caller's requested detector window;
- a five-day reverse posting is rejected even when the requested detector window
  is widened to fourteen days;
- an unresolved candidate is counted in the Sankey and Activity evidence before
  confirmation, and confirmation reduces the result to the purchase exactly.

The UI review path was also inspected in
`frontend/src/routes/transfers.tsx`. It explicitly labels unresolved pairs
`Needs review · counted`, confirmed pairs `Confirmed · excluded`, explains that
both posted sides must exist in linked-account history, states that unmatched
payments remain counted, shows reverse posting gaps, and provides Confirm and
Unpair actions on desktop and mobile. This matches the PI-06 coverage limitation
without silently suppressing a category.

## Boundary assessment

| Case | Expected | Result |
| --- | --- | --- |
| Evidence-qualified reverse card repayment, 2–4 days | One unconfirmed candidate | Pass |
| Same shape, five-day reverse gap | No candidate | Pass |
| Reverse equal amount without payment evidence | No candidate | Pass |
| Reverse checking-to-savings/payment-account shape | No card exception candidate | Pass |
| Two equally close qualified card receipts | No candidate | Pass |
| Ordinary forward pair within requested window | Candidate | Pass |
| Candidate before confirmation | Normal income/expense treatment | Pass |
| Confirmed linked repayment | Zero income/spending; no Sankey category | Pass |
| Card purchase paired with repayment | Purchase counted once | Pass |
| No covered counterpart | No invented pair; remains counted and coverage remains qualified | Pass |

The generic reverse-order equal-amount test in
`tests/test_transfer_detector.py::test_inflow_before_outflow_is_not_a_transfer`
was run unchanged and remains green. PI-19 was run unchanged; no test or
artifact contract was modified.

## Commands and results

```text
uv run --extra dev pytest -q \
  tests/test_pi20_card_payment_verifier.py \
  tests/test_pi19_card_payment_tdd.py \
  tests/test_pi07_card_payment_detection.py
12 passed, 2 warnings
```

```text
uv run --extra dev pytest -q
264 passed, 3 warnings
```

```text
cd frontend && npm test -- --run
54 passed
npm run typecheck
passed
npm run build
passed
```

The warnings are the repository's existing Starlette/httpx and SQLAlchemy
warnings. `git diff --check` passed. The roadmap scanner reported zero issues.

## Changed files

- `tests/test_pi20_card_payment_verifier.py` — independent adversarial and
  aggregate verification tests.
- `docs/roadmap/epics/020-product-integrity/tasks/PI-20.md` — completed status
  and execution log.
- this artifact — verification evidence and verdict.

No PI-19 file, PI-06 audit, or production implementation file was changed by
PI-20.

## Execution log

- 2026-09-09: Read PI-06 RCA, PI-07 implementation, PI-19 frozen contract, and
  CF-02 accounting contract. Confirmed PI-20 was evaluating the actual diagnosed
  layer.
- 2026-09-09: Added independent adversarial tests; initial test-authoring typo
  was corrected without changing any frozen contract. Focused verifier,
  PI-19, and PI-07 suites passed.
- 2026-09-09: Full backend (264), frontend (54), typecheck, build, diff check,
  and roadmap verification passed. Verdict: PASS; no escalation required.
