# Independent review brief — pending, not a verification verdict

Implementation source: `88216f5`; frozen red-contract commit: `11c1c61`.
Review this exact source plus documented follow-up commits, not the deployed
`4d2e2f1` consent/isolation-only runtime. No live investment endpoint calls.

## Scope

Run the backend suite from the implementation worktree using the project venv.
Tests forcibly use an isolated SQLite database and mocked Plaid. Check the frozen
20 tests without weakening their assertions, plus supplemental lifecycle tests.
Verify persisted rows, not just response counts. Inspect account/Item ownership,
per-product failure/locking, full pagination before mutation, correction/removal
window boundaries, complete versus missing values, unknown currencies and stale
observations. Probe source-token leakage in error responses/state.

Independently recompute fixture values: checking=100, investment account=1250,
holdings=1200 means net worth=1350, not 2550; bank expense stays 25. Simulate a
failed investment pull and verify bank sync remains functional. Check known/unknown
account classification, mutation rollback, replay, deletion/relink, schema replay,
missing account coverage and unchanged bank-only API shape. Review nullable value
compatibility before any UI/deployment release.

Record tested commit, commands, findings and verdict in INV-05-verification.md.
Do not mark independent approval based solely on implementer's green results.
No deployment, live billing, host configuration changes or financial data export.
