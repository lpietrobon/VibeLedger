# PI-08 — Sankey readability walkthrough

This artifact records the bounded visual correction for PI-08. The frozen
readability and accessibility contract remains in
[`PI-21-sankey-readability-tdd.md`](PI-21-sankey-readability-tdd.md); its tests
were not changed.

## Implemented behavior

- Sankey labels and amounts use an explicit 12px SVG font size rather than the
  prior 10px utility class.
- Labels keep a small gap from their node and use the available 640-unit
  viewBox width to truncate unusually long labels with an ellipsis. The full
  label remains available through `data-full-label`, `aria-label`, and a title
  when visual truncation occurs.
- Expandable income and bucket nodes retain their existing stable keys, pointer
  behavior, expansion callback values, and monetary values. They also expose
  button semantics and Enter/Space activation for keyboard users.
- Existing node/link titles and the net-refund explanation remain in place.
- The stable `HEALTH` bucket identity is preserved while its rendered label is
  descriptive (`Medical and pharmacy`) so it is not presented as an opaque
  all-caps code.
- No Sankey composition redesign was made: `Available cash` behavior remains
  unchanged for PI-09/PI-10.

## Deterministic viewport walkthrough

The PI-21 synthetic fixture was rendered in a 1280px-wide host and a 360px-wide
host. Both renderings include short labels, long labels, many categories, income
sources, category expansion, refund credits, savings, and deficit funding.

Observed contract results:

- Every rendered SVG text element reports `font-size="12"`.
- All label text stays within the 640-unit viewBox by the conservative geometry
  estimate used by the frozen suite; long labels expose truthful full-label
  evidence rather than silently changing their meaning.
- Income and bucket nodes expose stable `data-sankey-key` values, accessible
  names containing their formatted amounts, and keyboard activation callbacks.
- Exact bucket/category amounts, node identities, link titles, refund wording,
  and expanded income/category content remain present.

## Verification

- `cd frontend && npm test -- --run src/components/finance/charts/SankeyChart.test.tsx src/components/finance/charts/SankeyChart-readability-tdd.test.tsx` — **7 passed**.
- `cd frontend && npm test -- --run` — **63 passed**.
- `cd frontend && npm run typecheck` — passed.
- `cd frontend && npm run build` — passed.
- `python -m pytest tests/test_insights_analytics.py tests/test_cashflow_reporting.py tests/test_sankey_refund_credits.py tests/test_pi19_card_payment_tdd.py tests/test_pi20_card_payment_verifier.py -q` — **68 passed**, 2 existing deprecation warnings.
- `git diff --check` — passed.
- `python docs/roadmap/scan.py` — 0 issues.

No PI-21 test, artifact, fixture, accounting code, or PI-09 composition
recommendation was changed.
