# CF-13 Handoff Draft (2026-09-07)

## Current branch

- Repository: `lpietrobon/VibeLedger`
- Branch: `pr-22`
- Current commit: `2c740f2` (`Complete CF-14 Sankey test fixture`)
- Deployment: not performed; user will redeploy.

## Delivered and verified so far

- Trustworthy cashflow fixes through CF-14, including transfer-aware accounting,
  review workflows, refresh behavior, and refund-safe Sankey allocation.
- Backend: 234 tests passed; `app/` coverage is 88.75% statements, 77.26%
  branches, and 86.32% combined; CI gate is 81.34%.
- Frontend: typecheck passed, 44 tests passed, and production build passed.
- Streamlit synthetic walkthrough passed.

## Redeployment checklist (pending CF-11/CF-12 acceptance)

1. Back up the existing database.
2. Update to `pr-22` and install the documented backend/frontend dependencies.
3. Run the backend suite, frontend typecheck/tests/build, and the Streamlit
   walkthrough before starting the application.
4. Smoke-check Overview, Spending, Insights/Sankey, transaction review, and the
   refresh control using synthetic data first.
5. If a regression appears, revert the branch to the prior known-good commit;
   CF-14 has no schema migration or irreversible data operation.

Adding another linked account or more history can revise historical totals. After
syncing, review transfer matches, duplicate/unresolved queues, refund credits, and
the period coverage qualification before relying on a chart.

## Known limitation

Independent browser verification is not complete: the available verification
browser rejects local loopback with `net::ERR_BLOCKED_BY_CLIENT`. Automated UI
checks are green, but CF-13 must not be treated as a final verified handoff until
CF-11 and CF-12 are unblocked and accepted.
