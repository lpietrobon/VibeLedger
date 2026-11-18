# INV-06 execution handoff

Date: 2026-11-18
Coordinator: Charlie
Branch/worktree: `feat/investment-visibility` at `e963f73` before this handoff commit

## Recovered state

- INV-00–05 are done: spending isolation, frozen domain/ingestion contracts, dedicated investment ingestion, and independent fixture-level verification.
- Schwab Investments consent is live and exposes two brokerage accounts, one traditional IRA, and one Roth. INV-01 remains in progress because actual holdings/activity history, pricing/refresh behavior, billing, and Fidelity/workplace coverage are not fully validated. Do not claim those gates or call production provider endpoints as part of this slice.
- TIME-01 and TIME-02 are done. TIME-03 is now closed from existing independent evidence at `e963f73`; TIME-04 contains the frozen RED cross-screen suite, while TIME-05 remains separate routing work.
- Main deployment remains intentionally separate. This branch is development-only; do not deploy, mutate the real ledger, enable billing, or change provider consent.

## Execution order

1. **INV-06 — contract/design:** inventory current Overview and investment APIs/UI, publish the accepted UX/navigation contract, and close the task only with acceptance evidence. Prefer Investments in the Overview slot only if every unique Overview function has a documented reachable destination; otherwise retain Overview.
2. **INV-07 — RED tests:** use a separate test-author role/context. Freeze literal API/UI and interaction tests before implementation; record exact failing commands and source revision. Do not weaken existing money/spending/date contracts.
3. **INV-08 — implementation:** only after INV-07 is done and TIME-03 is done. Make the frozen tests green, preserving server-side money math, spending isolation, as-of/provenance/coverage disclosure, account/tax filters, and absent-vs-zero semantics.
4. **INV-09 — independent verification:** must be performed by a verifier other than the INV-08 implementer. Require actual responsive interaction evidence and an explicit M3 release verdict.

Do not skip status/assignment transitions, append-only execution logs, artifact links, scanner runs, source commits, or test evidence. Later INV-10+ work may begin only through normal dependency order after INV-09.

## Non-negotiable product direction

- Investment activity never contaminates Spending, operating income/cashflow, recurring, category/merchant analytics, or default Activity—even with include-transfers.
- Preserve bank-side transfer evidence and consolidated net-worth single counting.
- Never invent historical valuations, performance, freshness, coverage, zero balances, returns, or provider support.
- Shared account/date selections and exact effective bounds must drive cards, charts, tables, and drilldowns consistently.
- Browser money math is prohibited; financial summaries remain backend-owned.
- Use synthetic/redacted fixtures only. No credentials or personal holdings in source/artifacts.

## Verification baseline and host caveats

- Existing retained evidence at `e963f73`: 122 legacy frontend tests passed with intentional TIME-04 RED tests excluded; TIME-02 passed; typecheck passed. TIME-04 RED is expected until TIME-05 and is not an INV-08 oracle unless explicitly adopted through the dependency roadmap.
- A 2026-11-18 coordinator rerun could not complete on homepi: the roadmap scanner under system Python lacked `python-frontmatter`, and a combined Vitest invocation exceeded the 462 MiB tool memory bound. Use `/home/skywalker/VibeLedger/.venv/bin/python docs/roadmap/scan.py` (shared project venv) and split Vitest files or constrain workers. Record actual outcomes; do not report the interrupted run as a test failure.
- `frontend/node_modules` is untracked in this worktree. Do not commit it.

## Minimum closeout evidence per task

- Exact source commit and changed files.
- RED then GREEN commands where applicable, with frozen test integrity.
- Backend focused tests, frontend focused tests, typecheck/build as applicable, roadmap scanner, and whitespace/diff check.
- Explicit limitations and release/deployment status.
