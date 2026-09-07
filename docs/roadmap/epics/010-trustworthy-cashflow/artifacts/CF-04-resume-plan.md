# CF-04 — bounded test foundation handoff

2026-09-02. CF-01 and CF-02 are complete. The `test_foundation` helper was
dispatched, but the environment became unavailable before its report or test
results returned. No helper is currently running; do not assume its local edits
survived. This document preserves the intended small slice, not a completed result.

## Exact proposed slice

- Reuse only the deterministic clock change in `tests/test_recurring_api.py`
  and the five fake-SDK tests in `tests/test_plaid_client.py` from
  [the preserved original draft](CF-01-unpublished-draft.patch).
- Add a reusable test seeder/helper for the 20-row
  [CF-02 oracle](CF-02-ledger-fixture.json), with fixed expected results independent
  of production calculations. Keep executable helper code under `tests/`; no
  arithmetic-only placeholder tests or permanently failing/xfail accounting tests.
- Add `app/` statement+branch coverage configuration in `pyproject.toml`, with
  a justified gate preserving the baseline (combined 81.34%, no excluded lines).
  The user's 70–80% target is not a reason to lower existing measured quality.
- Add `.github/workflows/tests.yml`: isolated mocked backend tests/coverage and
  the existing frontend test, typecheck, and build commands. No production secrets,
  bank calls, deployments, or additional framework.
- Document commands, coverage denominator and limitations in `docs/testing.md`.

Ownership was limited to those files, a reusable test fixture/helper, and testing
documentation. No application, frontend, or roadmap edits were assigned to the
helper. The coordinator owns review, task logs, and publication.

## Validation and acceptance

Baseline application results are 156 passing tests and two time-dependent recurring
failures. Baseline frontend is 36 passing tests in four files. Selective clock and
fake-SDK tests should make this initial test slice green without importing the
separate sync draft that currently has a scheduler failure.

Run from the new checkout, with its installed dev/dashboard environment:

```bash
python -m pytest --cov=app --cov-branch --cov-report=term-missing --cov-report=json:coverage.json
cd frontend
npm test
npm run typecheck
npm run build
```

Inspect the diff and CI configuration, publish a small checkpoint, then verify the
actual GitHub Actions run. Record counts, statement/branch/combined coverage,
source scope and tested commit. If Actions or execution is unavailable, record the
specific limitation and leave acceptance open.

The old draft's 210 passed / 1 scheduler failure and 86.05% coverage are historical
snapshot evidence, **not results of this new slice**. Add regressions for the
unlanded accounting/sync fixes with those fixes in CF-05/CF-06/CF-07. Once CF-04 is
accepted, those tasks can start; do not force their dependencies done early.
