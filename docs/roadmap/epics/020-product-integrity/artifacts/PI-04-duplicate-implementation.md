# PI-04 — Duplicate correction implementation evidence

## Scope implemented

The manual duplicate relationship is represented by a dedicated durable table
with active, reversed, and invalidated states. The API validates the PI-03
eligibility rules before creating a relationship, exposes relationship labels on
ordinary transaction responses, and reverses without deleting source records.

Active duplicate exclusion is centralized in the shared posted-accounting
predicate and in the `effective_transactions` view. Consequently spending,
income, category totals, Sankey, recurring detection, and `is:spend` searches
exclude only the marked duplicate, while ordinary Activity/search still returns
both source records.

Provider modifications and removals invalidate the relationship. Item removal
retains its audit record and provider-identity evidence; historical relink can
reactivate it only when both identities resolve uniquely and the recorded date,
amount, account, and currency evidence still matches. Startup cleanup also
invalidates orphaned active endpoints.

## Verification

- `python -m pytest -q tests/test_pi15_duplicate_tdd.py` — **18 passed, 2 warnings**.
- `python -m pytest -q` — **248 passed, 3 warnings**.
- `git diff --check` — passed before commit.
- PI-15's test file and fixture were not modified during implementation.

The implementation was developed against the immutable PI-15 red result
recorded in [the PI-15 artifact](PI-15-duplicate-tdd.md): 17 feature failures
and one conservative no-automatic-hiding pass before production changes.
