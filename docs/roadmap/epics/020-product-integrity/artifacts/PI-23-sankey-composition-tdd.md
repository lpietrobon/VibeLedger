# PI-23 — Sankey composition TDD contract

This artifact freezes the accepted PI-09 adaptive-hub composition for PI-10.
The tests use synthetic `CashflowSankey` responses only. They do not read live
ledger data, reconstruct transaction accounting, or change production code.
PI-10 and PI-24 must run this suite unchanged. A required contract revision is
an escalation to the epic owner.

## Accepted adaptive-hub rule

The normal case is the server response with `netRefundCredits = 0` and
`deficit = 0`. In that case the chart must omit `Available cash` entirely:

- non-zero Income flows directly to positive spending buckets and, when
  applicable, Savings;
- Savings is omitted when its server-provided value is zero;
- zero-value buckets/categories and zero-value Income sources do not become
  drawable nodes or links.

When `netRefundCredits > 0` or `deficit > 0`, the chart retains `Available
cash` as an explicit exception allocation stage. Only non-zero sources and
destinations are shown. `Net refund credits` and `Deficit funding` remain
distinct from Income, and all visible links are non-negative.

An empty period has no drawable graph and must retain the existing companion
explanation (`No income or spending in this period.`). A zero-net category has
no drawable flow; its underlying transactions remain available through the
server/API evidence paths and are not silently converted into spending.

## Frozen fixtures and hand-checkable arithmetic

The cases below are the server payload values supplied to React. `P`, `C`, and
the derived values are recorded for review; the test oracle asserts explicit
server-provided amounts and expected graph links rather than recomputing raw
transaction/accounting logic in the client.

| Case | I | P | C | N | S | D | Required graph story |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Normal surplus | 3,000 | 900 | 0 | 900 | 2,100 | 0 | Income → FOOD; Income → Savings; no hub |
| Exact balance | 900 | 900 | 0 | 900 | 0 | 0 | Income → FOOD; no hub or Savings |
| Deficit | 900 | 1,200 | 0 | 1,200 | 0 | 300 | Deficit funding + Income → Available cash → FOOD |
| Refund credit | 3,000 | 90 | 120 | -30 | 3,030 | 0 | Net refund credits + Income → Available cash → FOOD/Savings |
| Refund-only with income | 3,000 | 0 | 120 | -120 | 3,120 | 0 | Net refund credits + Income → Available cash → Savings |
| Refund-only, zero income | 0 | 0 | 120 | -120 | 120 | 0 | Net refund credits → Available cash → Savings; no zero Income |
| Zero income with spending | 0 | 100 | 0 | 100 | 0 | 100 | Deficit funding → Available cash → FOOD; no zero Income |
| Zero spending | 1,000 | 0 | 0 | 0 | 1,000 | 0 | Income → Savings; no hub |
| Net-zero category | 1,000 | 0 | 0 | 0 | 1,000 | 0 | Income → Savings; zero category has no drawable flow |
| Empty period | 0 | 0 | 0 | 0 | 0 | 0 | No graph; companion empty-period explanation |

The fixture values satisfy the CF-14 identities reviewed in PI-09:

```text
N = P - C
S = max(I + C - P, 0)
D = max(P - I - C, 0)
```

For example, the refund-credit case is `3,000 + 120 = 90 + 3,030`, and the
deficit case is `900 + 300 = 1,200 + 0`. The test additionally rejects a
negative currency value in any rendered link title and checks that expected
link amounts are the exact values supplied in the fixture response.

## Stable identity and drilldown boundary

The test freezes the existing stable identity scheme needed by category
inspectability:

- `__income_node__` for Income;
- `bucket:<bucket>` for positive spending buckets;
- `cat:<category>` for expanded categories;
- `income:<category>` for expanded income sources;
- `__savings__`, `__available__`, `__refund_credits__`, and `__deficit__` for
  the named semantic nodes.

The expanded normal case must preserve `bucket:FOOD` and `cat:Groceries` while
changing only the bucket-to-category expansion path. The income-expanded case
must preserve `income:Salary`; neither expansion may reintroduce
`Available cash` into the ordinary composition or change the server-provided
money values.

## Test location and baseline

The frozen suite is:

```text
frontend/src/components/finance/charts/SankeyChart-composition-tdd.test.tsx
```

It renders each deterministic response, inspects literal rendered node keys,
link titles, and the empty-period companion text, and verifies the expanded
category/income identity paths. It does not use pixel snapshots or duplicate
the server's transaction-level accounting calculations.

Against the current pre-PI-10 chart, the focused red command was:

```text
cd frontend && npm test -- --run \
  src/components/finance/charts/SankeyChart-composition-tdd.test.tsx
```

Result:

```text
12 tests; 9 failed, 3 passed
```

The failures are expected. The current implementation always renders
`Available cash`, creates a zero-valued Income source/link, retains a zero-value
bucket, and attempts to lay out an all-zero graph. The passing exception cases
confirm that the fixture and link-title oracle can observe the already-valid
exception-stage behavior without weakening it.

The test runner emits the repository's existing React `act(...)` warnings and,
for the old all-zero graph, existing `NaN` SVG attribute warnings. These are
baseline observations for PI-10; they are not hidden by the contract.

## Execution log

- 2026-09-11: Read PI-09's accepted Design A recommendation, PI-07/PI-20's
  confirmed-versus-unresolved card-payment accounting boundary, PI-21/PI-22's
  stable key/value/readability contract, CF-14's refund identities, the current
  Sankey component and tests, and PI-10/PI-24.
- 2026-09-11: Added deterministic synthetic normal-surplus, exact-balance,
  deficit, refund-credit, refund-only, zero-income, zero-spending, net-zero,
  and empty-period cases. Added ordinary expanded-category and income-source
  identity checks.
- 2026-09-11: Focused red run produced **9 failed, 3 passed**. No production
  implementation, accounting code, or prior frozen TDD contract was changed.
- 2026-09-11: Existing frontend tests excluding PI-23, relevant backend
  Sankey/accounting tests, typecheck, and build were run; results are recorded
  in the task execution log.
