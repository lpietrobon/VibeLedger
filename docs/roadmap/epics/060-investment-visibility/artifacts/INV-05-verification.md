# INV-05 independent verification — 2026-11-15

Reviewer: independent `inv05_review` agent (not implementation author).
Source reviewed: `f1fee3f3c8efafbdb06a4883a5506417226b62da`.
Checkout HEAD: `a589468` (documentation-only delta from source). Frozen
`tests/test_investment_ingestion.py` unchanged from `11c1c61`.

## Verdict: changes required

Do not approve INV-05 or release live ingestion yet. The existing tests exercise
substantial isolation and atomicity behavior, but independent adversarial probes
found the following gaps. No live provider calls, deployment, settings or personal
data changes were performed.

### P2 — Accounts freshness metadata describes a different value

`app/api/routes.py:1557,1562,1579` uses mutable `Account.current_balance`
for account rows and net worth, but attaches freshness/observation metadata from
`InvestmentValuation`. After a successful fixture pull at 1250, simulate a later
independent account refresh setting current_balance=9999. Investment summary
correctly stays 1250; Accounts reports net worth=10099 (checking=100) with
investment freshness=`fresh` and the older investment observation timestamp.
Thus the provenance fix in f1fee3f does not extend to the consolidated consumer.
Use matching valuation/value provenance, or explicitly track and label independent
balance provenance; do not attach old holdings observation evidence to a new value.
Add a consumer-level regression, not only an investment_summary assertion.

### P2 — Conflicting security identities silently overwrite within one pull

`app/services/investment_sync.py:134-140` processes holdings securities followed
by activity securities without cross-response consistency validation. Provider
fixture holdings defines `fund` as mutual fund, while activity supplies the same
ID with name `Different security`, type `equity`. Sync returns success and stores
only the latter metadata. This contradicts the frozen contract's rejection of
security identity conflicts and the adapter's own cross-page check. Validate
same-ID records across the whole pull before mutation; reject incompatible
identity metadata atomically (ordinary changes across successive pulls can remain
supported). Add rollback assertions for holdings/activity and within-holdings
conflicting duplicates.

### P2 — Missing required page collection is converted into complete success

`app/services/plaid_client.py:85` defaults a missing `securities` collection to
empty. Mock SDK response `{'investment_transactions': [],
 'total_investment_transactions': 0}` returns a synthesized successful response
with `securities: []`. This bypasses `_apply`'s missing-collection guard and can
allow soft-removal reconciliation from a structurally incomplete response.
Require a list-valued securities collection on every page; preserve last-good
rows on malformed/incomplete provider payloads. Add adapter/service integration
regression with preexisting activity and verify no removal on this failure.

## Evidence and commands

Working directory: `/home/skywalker/VibeLedger-investments`.
Python: `/home/skywalker/VibeLedger/.venv/bin/python`.

- `git diff f1fee3f HEAD --stat`: documentation only.
- `git diff 11c1c61 HEAD -- tests/test_investment_ingestion.py`: empty.
- Project Python `docs/roadmap/scan.py`: 6 epics, 80 tasks, 0 issues.
  System Python lacks frontmatter; project venv works.
- Project Python `-m pytest -q`: running; result to be appended.
- Independent Python probe imported `tests.conftest` before application imports,
  ensuring temporary SQLite and mocked provider, then created fixture schema.
  Used `Provider`, `seed`, START/END from frozen tests. Injected the conflicting
  security record described above: sync success, catalog overwritten. Updated
  broker balance to 9999: summary 1250, Accounts net worth 10099 with fresh
  observation. Mocked adapter page without securities: returned empty successful
  collections. All three observed, not merely theoretical source findings.

## Other reviewed boundaries

The service validates before final commit and rolls back apply errors; state is
separate from bank sync. Holdings/activity use dedicated tables. Full page reads
precede apply; repeated IDs, changing totals and premature empty pages are rejected.
Removal is bounded by dates and present accounts. Absent accounts retain rows and
receive missing coverage. Item removal explicitly cleans investment-owned rows.
Missing valuation and unsupported currency withhold investment summary totals.
There is no UI approval or real-provider history/billing evidence in this review.
A persisted running lock has no crash-recovery lease; document a safe recovery
procedure or add bounded recovery before operational rollout (nonblocking follow-up
for this fixture-development slice).

## Final independent regression result

`/home/skywalker/VibeLedger/.venv/bin/python -m pytest -q`:
**394 passed, 2 warnings in 99.00 seconds**. Warnings are Starlette/httpx
deprecation and the existing TransactionAnnotation identity-map warning.
No frozen tests or implementation files were edited by the reviewer. Green
existing tests do not cover the three independently reproduced findings above;
verdict remains changes required.

## Independent re-review — 2026-11-15

Reviewer: independent `inv05_recheck` agent, not implementation author.
Candidate: `4169dca9641a3a0369926438b1e79ad1a6b651c2`.

**Verdict: approved for the fixture-driven INV-05 ingestion/isolation slice.**
All three prior P2 findings are resolved in this candidate. This supersedes the
initial changes-required verdict for this source revision only; it is not live
provider, billing, UI, or deployment approval.

- Accounts now obtains both investment value and currency from the same observed
  valuation used by its coverage metadata. Independently changed mutable account
  balance to 9999 and currency to EUR after observing 1250 USD: Accounts still
  returned net worth 1350 and investment currency USD.
- Whole-pull security consistency is validated before account mutation, including
  holdings/activity disagreement and duplicate holdings securities. Independent
  conflict injection preserved the original security catalog, marked sync error,
  and made freshness stale. A subsequent normal metadata correction on a later
  pull succeeded, confirming that the guard does not prohibit ordinary updates.
- Every activity page requires list-valued securities. The adapter/service
  regression exercises a missing collection with prior persisted activity and
  verifies rejection without removal. Source inspection confirms the guard applies
  on every page before any service application, including null/non-list values.
- Reviewed atomic rollback/error state, observed-value consumers, and regression
  coverage. No implementation or frozen-test changes were made by this reviewer.

Commands/evidence from `/home/skywalker/VibeLedger-investments`:

- `/home/skywalker/VibeLedger/.venv/bin/python -m pytest -q`:
  **398 passed, 2 warnings in 101.16s**. Same Starlette/httpx deprecation and
  pre-existing TransactionAnnotation identity-map warning.
- `git diff 11c1c61 HEAD -- tests/test_investment_ingestion.py`: empty.
- Project Python `docs/roadmap/scan.py`: 6 epics, 80 tasks, 0 issues.
- Additional independent Python probes imported `tests.conftest` first, used its
  isolated SQLite engine and synthetic Provider, and asserted value/currency
  provenance, catalog rollback, error freshness, and successful correction/retry.

The previously noted crash-recovery procedure remains an operational follow-up
before rollout. INV-01 live coverage/pricing and later consumer/UI acceptance
remain separate gates. No provider calls, live data access, deployment or host
configuration changes were performed.
