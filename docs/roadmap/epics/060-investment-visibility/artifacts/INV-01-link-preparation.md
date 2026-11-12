# Investment Link preparation — 2026-11-11

Internal preparatory adapter only; not a delivered connection flow.

User authorized advancing implementation until owner input is needed. Prepared
`PlaidClient.create_investment_link_token` under the coverage spike, without
claiming downstream tasks or live coverage complete. It requests only Investments
for a NEW connection, preserves OAuth redirect/country settings, and makes no
exchange, sync, or database calls. Existing bank Link remains unchanged.
No route/UI calls this method. Do not use it to replace the existing Schwab Item.

## Evidence

Fake SDK tests in `tests/test_investment_link.py` freeze investment-only products,
absence of bank history configuration, unchanged bank Link, OAuth redirect,
provider failure propagation and visibly synthetic mock output.
Red baseline: 4 missing-method failures, 1 bank regression pass.
These tests do not prove live entitlement, institution/account support, spending
isolation after ingestion, or a functioning end-to-end connection flow.

## Owner input required

In the Plaid dashboard for this application's Production environment, confirm:

1. Investments access is approved, including any Fidelity/Schwab access conditions.
2. The applicable subscription/usage pricing is acceptable and activation is authorized.

A redacted status summary is enough; do not share credentials. Availability on an
existing Item is not an entitlement or pricing check. Actual account selection and
OAuth consent must ultimately be completed by the owner.

## Remaining implementation after the access gate

- Verify current existing-Item update-mode parameters for additional Investments
  consent/account selection. Bind the local connect session to that Item; update
  completion must not exchange a new public token or insert a duplicate Item.
- Freeze INV-02's account-domain contract and implement/test INV-03/04 isolation
  before exposing investment linking or ingestion in production. Dedicated holdings
  and activity tables must not feed canonical spending queries; include-transfers
  must not bypass the boundary. Mixed Items require account-level classification.
- Preserve checking funding evidence and net-worth single counting. Separate
  balance/investment sync failure from bank transaction sync failure.
- Add route/UI intent, expiry/replay tests, and independent verification before
  deployment. No Overview removal is included in this preparatory change.

The roadmap explicitly requires INV-01 completion before INV-02–04 start. Its
live coverage gate remains open, not silently waived by synthetic tests.

Validation: full backend suite (`python -m pytest -q`) passed: **350 tests**, two
existing warnings (Starlette/httpx and SQLAlchemy identity map). Roadmap scanner:
6 epics, 79 tasks, 0 issues. `git diff --check` passed. Implementer verification
only; no independent review or deployment claimed.
