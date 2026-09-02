# Testing

From the repository root, using its Python 3.12 environment:

```bash
python -m pip install -e '.[dev,dashboard]'
python -m pytest --cov --cov-report=term-missing --cov-report=json:coverage.json
cd frontend
npm ci
npm test
npm run typecheck
npm run build
```

Coverage includes all `app/` statements and branches, with no source omissions.
The gate is **81.34% combined**, preserving the measured pre-hardening baseline
(83.93% statements / 71.64% branches). This is backend coverage; it does not claim
React or Streamlit coverage. Improve critical scenario coverage even when the
percentage passes. Snapshot measurements and accepted runs belong in the CF-04
log; a failing suite is not successful just because coverage passes.

Tests use isolated SQLite databases and mock Plaid. Provider adapter tests inject
a fake SDK transport and never contact a bank. `.github/workflows/tests.yml` runs
the backend gate and the existing frontend test/typecheck/build checks separately.
The workflow publishes a coverage artifact; it does not deploy the application.

`tests/cashflow_fixture.py` seeds the CF-02 ledger, including confirmed transfer
pairs, the pending record, and the refund's purchase link. Its oracle is the
independently authored JSON under the epic's artifacts. Import
`seed_cashflow_ledger` in a test, seed a database session, commit, and use the
returned stable IDs and fixed expectations to exercise API/service behavior.
Alternatively import the `cashflow_ledger` pytest fixture into a test module.

Add regressions alongside fixes to observable accounting or lifecycle behavior.
Assert expected totals and contributing evidence rather than reproducing production
calculations. Do not add permanent expected-failure tests for unlanded fixes, or
weaken expectations to match current defects. CF-05/06/07 own their integration
scenarios; CF-10 and CF-11 provide separate independent acceptance.
