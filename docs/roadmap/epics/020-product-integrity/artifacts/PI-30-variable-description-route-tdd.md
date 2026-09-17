# PI-30 — variable-description confirmed-route reconciliation

## Privacy boundary

This artifact and `tests/test_pi30_variable_description_route_tdd.py` use only
synthetic accounts, identifiers, descriptions, dates, categories, and amounts.
They contain no copied, aggregated, derived, hashed, or otherwise encoded live
ledger data.

## Frozen TDD contract

The test module freezes a narrow route-evidence rule for a previously manually
confirmed directed checking-to-card repayment route:

1. The newly matched movement remains exact, mutually unique, opposite-signed,
   active-linked, and currency-compatible.
2. Its checking outflow has explicit structured provider payment evidence.
3. Its card-side counterpart has no structured transfer claim but retains an
   exactly stable payment description.
4. The checking description differs from the manually confirmed predecessor
   only at one explicit four-digit `REF` token.

The automated decision records `confirmed_route_stable_leg` evidence without
persisting raw descriptions or reference values. This is not digit stripping,
fuzzy matching, or an account-route allowlist. Account suffixes, dates,
arbitrary numeric prose, changed nonnumeric text, a different route, weak
provider evidence, ties, rejection memory, manual decisions, and source
changes all abstain or preserve the existing safe lifecycle behavior.

## Red-to-green evidence

Focused contract command:

```text
.venv/bin/pytest -q tests/test_pi30_variable_description_route_tdd.py
```

Before the PI-30 evidence implementation, the positive automatic-confirmation,
candidate-redetection, no-delta-refresh promotion, source-revalidation, and
accounting assertions were red because the detector only recognized exact
two-sided descriptions. The negative controls already represented the required
abstention boundary. After the implementation, the focused contract passes.

## Implementation and verification

`app/services/transfer_detector.py` now accepts the new evidence only after a
manual confirmation of the same directed accounts. It requires an exact stable
card-side leg, structured evidence on the changing checking-side leg, and a
single named bounded reference token. Automatic decisions are not used as
future route-training data and revalidation removes the decision if qualifying
source evidence changes.

The contract exercises direct detection, redetection of an existing review
candidate, and successful sync with zero imported changes. It also verifies
that only the strong pair is excluded from Activity and Sankey accounting; weak
or ambiguous pairs remain counted and reviewable.

Commands:

```text
.venv/bin/pytest -q tests/test_pi30_variable_description_route_tdd.py tests/test_pi27_generic_transfer_reconciliation_tdd.py tests/test_pi28_generic_transfer_implementation.py tests/test_pi19_card_payment_tdd.py tests/test_transfer_detector.py
.venv/bin/pytest -q
.venv/bin/python docs/roadmap/scan.py
git diff --check
```

## Change control

The PI-30 test module is the accepted oracle for this route-evidence shape.
Future changes must not weaken it; expanding to other description grammars or
evidence classes requires a separate roadmap task and privacy-safe synthetic
contract.
