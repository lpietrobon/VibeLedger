# Recovered agent work — 2026-09-02

## What exists and what is accepted

Earlier agent work produced substantial ingestion, accounting, frontend, and test
drafts. Some implementers reported finishing their assigned slices; that is not
completion of the subsequently created CF tasks. No application changes from this
work have been applied to `pr-22`, no task has passed final acceptance, and no
earlier subagent is currently running. All assignments remain null.

The available record comprises the earlier session handoff, the surviving local
diff, saved backend logs, and the fresh checks below. Original per-agent reports
and temporary independent-verifier scripts were not recovered. Do not attribute
every file to an individual agent or treat reported verifier success as a signed
acceptance result. The fresh checks were run by the coordinator; they are not a
replacement for the independent verification tasks.

## Recoverable draft

- Base: `3b9c8c922b7db22597a7ac74c3b3bb63554a820c`.
- Published roadmap head before this update: `97bec0b9e1674f4ca543c12d24fd09a61d166e90`.
- [Draft patch](CF-01-unpublished-draft.patch): 44 modified files and 7 new files,
  captured together from the surviving working tree. This is a review artifact,
  not code installed in the application tree.
- [Manifest](CF-01-draft-manifest.json): exact file list, per-file SHA-256, and
  patch SHA-256. The patch passed `git apply --check` against a clean base checkout.
- Snapshot SHA-256: `0e1380e6ac88ee7bb169ed2dd2299dab0d724f3e4d6c8781d35ba6248f37cfb6`.

Inspect or recover it in a separate worktree at the base commit. Do not apply it
wholesale to the current branch: its README/CLAUDE/old-roadmap edits predate the
new roadmap, and its application changes remain under review. Selectively port
verified changes through the tasks below. Retain this original snapshot as
evidence; later revisions should get a new artifact name, not overwrite it.

## Progress by workstream

| Earlier workstream | Evidence recovered | Task mapping | Remaining acceptance |
|---|---|---|---|
| Coordinator/baseline audit | Original baseline log, draft inventory, policy notes, new recovery checks | CF-01, CF-02, CF-04 | Finish provider/history inventory and accounting decision table |
| Ingestion implementer | Draft sync atomicity, provider-ID updates, pending replacement, annotation preservation, rule application, relationship cleanup; regression tests | CF-05, parts of CF-04/CF-07 | Resolve scheduler failure, review repeated-link coverage, integrate and independently verify |
| Accounting/reconciliation implementer | Shared posted accounting/period helpers, confirmed-only transfer exclusion, conservative pairing, refund/category/API/SQL parity; synthetic tests | CF-06, CF-07, parts of CF-02/CF-04 | Review policy edge cases, currency limitations, mutations and final integration |
| Frontend implementer | Period-aware comparisons/drill-downs, cache invalidation, review feedback, chart guards; new tests | CF-08, CF-09 | Browser walkthrough, supported-dashboard parity, incomplete-history UX and recurring review acceptance |
| Earlier independent verifiers | Session handoff reports conservation and sync smoke checks plus chart/refund issues that informed drafts; original scripts/results unavailable | CF-10, CF-11 | Recreate independent evidence on a pinned integrated commit; no final sign-off recovered |
| Coordinator/test/documentation work | Draft CI workflow, coverage configuration, README/CLAUDE updates | CF-04, CF-12, CF-13 | Green suite/actual CI run, maintainability review, reconcile old docs and final handoff |

## Reproduced test evidence

Commands run from the draft repository, using its installed environment:

```bash
.venv/bin/python -m pytest --cov=app --cov-branch --cov-report=term --cov-report=json:coverage.json
cd frontend
npm test
npm run typecheck
npm run build
```

The recovery run wrote its JSON outside the repository; the name above is a
portable equivalent. Backend fixtures use a temporary database and mocked Plaid.
The frontend build is a local build, not a deployment.

| Snapshot | Backend tests | Statement coverage | Branch coverage | Combined coverage |
|---|---|---:|---:|---:|
| Original base | 156 passed, 2 failed | 83.93% | 71.64% | 81.34% |
| Earlier saved draft run | 204 passed, 1 failed | 88.10% | 78.29% | 85.99% |
| Recovered draft, fresh run | 210 passed, 1 failed | 88.22% | 78.19% | 86.05% |

Coverage is measured over `app/`, with zero excluded lines in these reports. It
does not measure React or Streamlit UI coverage. Changes in source/test counts
mean these are observed snapshot results, not identical-denominator experiments.
The draft's 80% combined gate passes, but the overall backend command **fails**.
The original baseline failures are two date-dependent recurring API tests; those
tests pass in the recovered draft.

Fresh frontend result: **48 tests across 5 files passed; typecheck and build
passed**. This establishes automated checks, not completed browser/user research.

Evidence: [baseline backend log](CF-04-baseline-backend-tests.txt),
[fresh backend log](CF-04-draft-backend-tests.txt),
[fresh frontend log](CF-04-draft-frontend-checks.txt), and
[coverage totals/metadata](CF-04-coverage-summary.json).

## Concrete remaining issues and next actions

1. **CF-05/CF-04: failing multi-item scheduler test.**
   `tests/test_scheduler.py::test_sync_all_items_syncs_active_items` fails because
   the second item encounters `ValueError: account belongs to a different linked
   item`. The fixture uses the same token for two items and the mock returns the
   same account ID, while the draft now guards cross-item identity. Resolve the
   mock/test contract and verify real repeated-link behavior; do not simply remove
   the identity guard or dismiss the failure as harmless.
2. **CF-01/CF-02: complete scope evidence.** Actual Venmo availability, duplicate
   account coverage, incomplete-history semantics, and unsupported mixed-currency
   aggregation are not established by synthetic fixtures. A linked account named
   `venmo` is not proof of a working connector. Complete the compact decision table
   and supported/unsupported inventory before accepting implementations.
3. **CF-03/CF-08/CF-09/CF-11: finish the UX evidence.** Source-level fixes and
   automated tests exist; no complete browser walkthrough, mobile/accessibility
   assessment, or user research report was recovered. Existing duplicate/suspicion
   detection support and recurring workflows still need the scoped audit.
4. **CF-10/CF-12: independent review and final verification.** The earlier
   independent smoke-check reports were provisional and not tied to this exact
   snapshot. Re-run independent ledger and UI acceptance after integration;
   maintainability/migration review and an actual GitHub CI run remain outstanding.
5. **CF-13: reconcile docs and publish only accepted implementation.** Draft
   documentation contains premature statements such as CI being enforced, although
   the workflow is unpublished. Update it against the final verified behavior and
   preserve the new roadmap. User redeployment remains a separate later action.

The first eligible work remains CF-01; CF-02 and CF-03 follow its acceptance.
Implementation-bearing tasks with unfinished prerequisites are now `blocked` and
link this evidence. This records historical partial progress without declaring
their prerequisites done or inventing a new status. `todo` on early audit/UX tasks
means not accepted and not currently assigned, not that every investigation must
be repeated. Resume from the evidence and close only the remaining gaps.
