# PI-21 — Sankey readability and accessibility TDD contract

This artifact freezes the observable rendering boundary for PI-08. It is
deliberately red against the current Sankey implementation: PI-08 may change
presentation code to satisfy these tests, but may not weaken or silently revise
the contract. The tests use synthetic values only and do not encode a new
accounting or grouping policy.

## Scope and fixtures

The focused suite is
`frontend/src/components/finance/charts/SankeyChart-readability-tdd.test.tsx`.
It renders one deterministic response at both of these host widths:

| Fixture | Host width | Host height | Purpose |
|---|---:|---:|---|
| wide | 1280px | 900px | desktop presentation with room for labels |
| narrow | 360px | 760px | phone-width presentation where the fixed 640-unit SVG viewBox is stressed |

The response deliberately includes:

- two income sources, with an income-expanded render;
- five spending buckets and many category rows, with `FOOD` expanded;
- short names and long names such as “Home improvement and household
  maintenance” and “Groceries and household supplies”;
- `Net refund credits` and its explanatory copy;
- `Savings` and positive deficit funding in the same exceptional fixture.

The fixture values are synthetic and hand-checkable. The test asserts that the
values and keys survive rendering, not that the client recomputes accounting.

## Frozen observable contract

The implementation must satisfy all of the following at both viewport widths:

1. Every rendered node label and amount uses a rendered SVG font size of at least
   12px. This is a minimum legibility floor, intentionally materially above the
   current `text-[10px]` class; the contract does not prescribe a particular
   font family, weight, or exact layout.
2. Expandable nodes expose a stable `data-sankey-key`, `role="button"`,
   `tabindex="0"`, and an accessible name containing the displayed monetary
   value. Enter and Space activate the same `onToggle` path as pointer
   activation, preserving the existing income/category expansion behavior.
3. Every label exposes its complete semantic name through `data-full-label`.
   If its visible text is truncated, its accessible name and native SVG title
   retain the complete name. Visible text must remain within the 640-unit
   viewBox according to the test's conservative, deterministic text-width
   envelope; clipping or overlap cannot silently change a category name.
4. Stable bucket keys, expanded category keys, and income-source keys remain
   present. The rendered output retains the exact synthetic amounts for bucket,
   category, refund-credit, and deficit flows. The chart may alter typography,
   spacing, wrapping, or truthful truncation, but not money values, category
   identities, grouping, or expansion semantics.
5. The existing refund explanation and link/title evidence remain available;
   this task does not hide refund credits, deficit funding, or categories to
   improve appearance. PI-09's composition decision is outside this contract.

The tests intentionally avoid pixel-perfect screenshots and browser-specific
font rasterization. The geometry assertion is a conservative semantic envelope
around the rendered SVG text, while the DOM/SVG assertions directly inspect
keys, names, activation, values, and explanatory text.

## Baseline observation

The current `SankeyChart.tsx` renders labels with the literal class
`text-[10px]`, places labels six SVG units from nodes, gives node rectangles and
text no stable DOM key/accessibility role, and has no keyboard handler. It also
renders full long strings without a full-label/truncation contract. The current
implementation therefore fails the minimum label-size, accessible-node,
truthful-label metadata, and stable-key expectations before PI-08 changes.

Against the pre-PI-08 implementation, the focused red command was:

```text
cd frontend && npm test -- --run src/components/finance/charts/SankeyChart-readability-tdd.test.tsx
```

Result:

```text
6 failed, 0 passed
```

The two viewport cases fail on the absent `font-size`/10px baseline. The
accessibility case fails because the current SVG has no keyed interactive node
element. The two viewport geometry cases fail because labels have no
`data-full-label` contract (and the current long-label treatment has no
truthful truncation or clipping guarantee). The value/key case fails because
the current markup does not expose stable Sankey keys for the rendered nodes.

The existing `SankeyChart.test.tsx` remains a separate passing regression for
refund-credit explanation behavior. PI-21 does not replace it.

## Verification log

- 2026-09-11: Read PI-08, PI-09, PI-22, current `SankeyChart.tsx`, the existing
  Sankey test, and roadmap conventions. No production code was changed.
- 2026-09-11: Added deterministic wide/narrow synthetic fixtures and the frozen
  DOM/SVG TDD cases described above.
- 2026-09-11: Focused suite intentionally red: `6 failed, 0 passed`.

