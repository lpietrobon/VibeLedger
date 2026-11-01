# PI-24 — Sankey composition verification

## Scope and immutable contract

- Tested checkout: `765082b`.
- PI-23 contract is unchanged from PI-10 commit `9386d16` (object
  `b4a4526c5fd3628abf45c3b250c82225208fb99a`).
- `npm --prefix frontend test -- --run
  src/components/finance/charts/SankeyChart-composition-tdd.test.tsx` — 12
  passed.

## Reconciliation verdict

The frozen synthetic cases cover the normal direct Income-to-spending/Savings
story, exact balance, deficit funding, refund credits, zero-income, zero
spending, net-zero category, empty period, and category/income expansion.
Their literal arithmetic is retained in the immutable PI-23 artifact. The
passing graph assertions confirm that refund credits are distinct from income,
deficits are explicit, links are non-negative, and stable category keys remain
available for inspectability work.

No product repair or TDD-contract change was required.
