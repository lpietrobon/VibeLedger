---
id: 020-product-integrity
title: Product integrity and cleanup
status: planned
owner: null
created: 2026-09-08
revision: 3
---

## Goal

Remove obsolete product paths and correct the known inconsistencies that make the
existing deterministic VibeLedger experience harder to trust or maintain. This
epic does not introduce a new product direction; it retires Streamlit, closes
specific accounting and review gaps, and makes established React behavior more
consistent. [The spirit of this epic](spirit.md) is the durable statement of
intent.

## Scope Notes

- React is the only product UI after this epic. Remove Streamlit application code,
  configuration, tests, dependencies, commands, and current documentation, while
  retaining backend behavior still used by React or the API. Historical roadmap
  logs and artifacts remain as audit history and must not be rewritten merely to
  erase past Streamlit references.
- Make equivalent category summaries on Overview and Spending lead to equivalent
  posted-spending evidence in Activity, using one filter-construction path.
- Add a reversible manual correction for two imported records that represent one
  real transaction. Preserve both source records and a structured canonical-to-
  duplicate relationship; exclude only the record explicitly marked duplicate.
  Similar-looking rows remain counted unless the user resolves them.
- Diagnose the observed credit-card-payment contribution to Sankey before changing
  accounting. Preserve epic 010's rule that confirmed linked-account repayments
  add no spending; make unresolved and missing-counterpart cases explicit.
- Generalize the diagnosed transfer remedy across all linked accounts. Deterministic,
  mutually unique pairs with strong two-sided evidence may be confirmed
  automatically; ambiguous, incomplete, unequal, or one-sided movements remain
  counted and reviewable. Account type may corroborate a match but must not define
  the linked-account boundary or act as the sole auto-confirmation signal.
- Improve Sankey label readability and simplify its common-case cashflow story,
  while representing refund-credit and deficit exceptions truthfully.
- Standardize ordinary textual dates across React using the current-year-aware
  product format. Chart axes and tooltips are outside this formatting rule.
- For each code-changing slice, keep the accepted behavior cases separate from
  implementation: a TDD task writes and records the failing contract, the
  implementation task makes those cases pass unchanged, and an independent
  verifier may repair product code but must escalate any proposed test change.
- Do not add an LLM agent, automatic duplicate hiding, new provider integration,
  investment analysis, or a broad visual redesign.

## Revision Log

- rev 3 (2026-09-13): Add a generic, high-precision automatic transfer-
  reconciliation chain after live use showed that requiring manual confirmation
  for every strong match leaves otherwise-correct cashflow views difficult to
  trust. Preserve two-sided evidence, auditability, reversal, and abstention for
  ambiguity; do not limit the solution to credit-card repayments.

- rev 2 (2026-09-08): Decompose each code-changing slice into a test-first task,
  implementation task, and independent verifier. The verifier may fix product code
  but may not revise the accepted TDD contract without escalation.

- rev 1 (2026-09-08): Initial cleanup and product-integrity scope, based on
  `main` after PR #22 was merged.
