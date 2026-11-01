# PI-10 — Sankey composition implementation

## Implemented contract

PI-10 implements the accepted adaptive allocation-hub design from PI-09 and the
frozen PI-23 contract. The server remains the source of all monetary values and
accounting semantics; this change only chooses the presentation graph's existing
paths and omits nodes that carry no drawable value.

- In the ordinary case (`deficit = 0` and `netRefundCredits = 0`), Income links
  directly to positive spending buckets and to Savings when Savings is positive.
  `Available cash` is absent.
- In an exceptional case (`deficit > 0` or `netRefundCredits > 0`),
  `Available cash` remains an explicit allocation stage. Income, Net refund
  credits, and Deficit funding enter it only when their server-provided values are
  positive; spending buckets and Savings leave it using their server-provided
  amounts.
- Net refund credits remain labeled and explained as residual credits after
  same-category netting, not as Income. Deficit funding remains explicitly named
  and is not presented as earned Income.
- Zero-value buckets/categories/sources and zero-value Savings are not drawable
  nodes. An empty response avoids invoking d3-sankey on an empty graph and keeps
  the existing `No income or spending in this period.` explanation.
- Existing stable identities (`__income_node__`, `bucket:<bucket>`,
  `cat:<category>`, `income:<category>`, `__available__`, `__refund_credits__`,
  `__deficit__`, and `__savings__`) remain intact whenever the corresponding
  semantic node has a positive drawable flow. Expanded bucket/category and
  income-source paths continue to use their existing keys and server amounts.

## Implementation boundary

Only `SankeyChart.tsx` changed. The component now derives a local allocation target
from the presence of exceptional server values and uses it for the already-defined
bucket/category and savings links. It does not reconstruct transaction-level
accounting, recalculate refunds, alter transfer treatment, or change API shapes.
The empty-graph guard prevents d3-sankey's layout routine from receiving a graph
with no links, which also removes the prior all-zero SVG warning path.

## Verification evidence

The immutable PI-23 contract suite was run unchanged:

```text
cd frontend && npm test -- --run \
  src/components/finance/charts/SankeyChart-composition-tdd.test.tsx
```

Result: **12 passed**. Combined focused regression run including the existing
Sankey test and PI-21 readability suite: **19 passed**.

```text
cd frontend && npm test -- --run
```

Result: **75 passed**.

```text
cd frontend && npm run typecheck
cd frontend && npm run build
```

Both passed. The full backend suite also passed:

```text
uv run --extra dev pytest -q
```

Result: **267 passed**, with three existing dependency/SQLAlchemy warnings. The
roadmap scanner reported zero issues and `git diff --check` passed.

## Case coverage

PI-23's synthetic server-response fixtures cover normal surplus, exact balance,
deficit, refund credit, refund-only with and without Income, zero-Income spending,
zero spending, net-zero category, and an empty period. They verify literal link
titles, non-negative drawable values, empty-period copy, and stable expanded
bucket/category/income-source keys. The implementation passes these cases without
altering the frozen test or its oracle.

## Execution log

- 2026-09-11: Inspected PI-09's recommendation, PI-23's immutable contract,
  PI-08/PI-21 readability constraints, PI-07/PI-20 accounting outcomes, CF-14,
  the current Sankey component, and current Sankey tests.
- 2026-09-11: Implemented adaptive normal-versus-exception composition, filtered
  zero-value drawable nodes/links, preserved existing keys/amounts/expansion, and
  added an empty-graph layout guard. No test contract or backend code changed.
- 2026-09-11: Focused composition/readability/regression tests passed (19); full
  frontend tests passed (75); typecheck, build, full backend (267), and diff check
  passed. Roadmap scan reported zero issues.
