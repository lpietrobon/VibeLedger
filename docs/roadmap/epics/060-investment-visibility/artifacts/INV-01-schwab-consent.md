# Schwab-first consent preparation — 2026-11-11

Owner supplied a Plaid Products screenshot showing Investments **Enabled** and
requested starting with Schwab. This resolves team product enablement, not actual
brokerage coverage, pricing units, or account-level OAuth consent. Fidelity is
not part of the first live validation. Optional Investments Refresh is not used.

## Implemented on the development branch

- Authenticated `POST /items/{item_id}/investments/connect` binds a short-lived
  session to an existing active Item. No replacement Item or token exchange.
- Update Link uses existing access token, `additional_consented_products` set to
  Investments, and `update.account_selection_enabled=true`; omits `products`.
- Completion permits absent public token for update mode and verifies consent
  using provider metadata. It does not fetch holdings, initialize Investments,
  refresh accounts into the ledger, or call bank sync.
- Existing bank sessions retain public-token requirements. Legacy sessions gain
  `purpose=bank` through an idempotent additive schema patch.
- Expiry, replay, missing Item, provider error redaction, migration replay, default
  disabled gate and post-consent teardown failure are covered by synthetic tests.
- A teardown failure reports consent success with `cleanup_pending=true`, not a
  false connection failure. Operational cleanup must still be performed.

Provider contract checked against https://plaid.com/docs/link/update-mode/ on
2026-11-11, especially “Requesting additional consented products.” Provider docs
say added products are billed when the corresponding data endpoints are called;
this is not a confirmation of the owner's plan or unit pricing.

## Release boundary

`INVESTMENT_LINK_ENABLED` defaults to false. Do not enable or deliver a production
consent URL yet: the existing scheduler's bank sync can discover newly consented
investment accounts, even though the consent handler itself does no ingestion.
Server-side isolation must be implemented and verified first. No production config
was changed, no service restarted, and no live link token created by this change.

INV-01 remains in progress. Synthetic consent preparation is not completion of
INV-02–05 or actual Schwab holdings/history validation. Subsequent work must resolve
the roadmap's circular dependency (live coverage requires safe consent, whose
isolation currently depends on completing live coverage) explicitly, without
marking unverified coverage done.

## Evidence

Initial targeted baseline: three expected failures (missing adapter/route and
absent update callback schema). Targeted final tests: eight passed in
`tests/test_investment_update.py`. Independent working-diff review checked consent
semantics and identified teardown misreporting; fixed with a regression test.
No live OAuth, UI delivery or production schema verification claimed.

Final source verification: `31b81fd` — full backend suite **358 passed**, two
existing warnings (Starlette/httpx and SQLAlchemy identity map); roadmap scan
6 epics/79 tasks, zero issues; diff whitespace check passed. Independent reviewer
rechecked this committed source and all eight update tests, approving only the
preparatory consent slice. Default-off gating prevents session creation, not
revocation of previously issued sessions. Source pushed to the implementation
branch; no deployment. Next engineering work: domain isolation before live consent.
