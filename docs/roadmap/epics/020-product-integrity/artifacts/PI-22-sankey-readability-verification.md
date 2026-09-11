# PI-22 — Sankey readability independent verification

This artifact records the independent verification of PI-08 against the frozen
PI-21 rendering and accessibility contract. The verification used the synthetic
PI-21 fixture only; no private ledger data was involved.

## Scope and tested implementation

- Tested PI-08 commit: `0a3d067` (`Improve Sankey label readability`).
- Frozen contract: `PI-21` and
  `frontend/src/components/finance/charts/SankeyChart-readability-tdd.test.tsx`.
- Implementation inspected:
  `frontend/src/components/finance/charts/SankeyChart.tsx`.
- Composition was not changed. `Available cash` remains governed by PI-09/PI-10.
- PI-21's test, fixture, artifact, and task were not modified.

## Viewport and fixture evidence

The unchanged PI-21 fixture was rendered at both supported host sizes:

| Fixture | Host size | Observed result |
|---|---:|---|
| wide | 1280 × 900 | 12px SVG labels and amounts; long labels remain inside the 640-unit viewBox or expose full-label evidence; keys, values, expansion, titles, and refund explanation preserved |
| narrow | 360 × 760 | same semantic and geometry contract passes under the phone-width host; no essential text is clipped by the fixed viewBox envelope |

The fixture exercises short and long labels, many categories, income-source
expansion, category expansion, refund credits and their explanation, savings,
and deficit funding. The rendered label implementation uses a measured
viewBox-aware truncation envelope and retains complete names through
`data-full-label`, `aria-label`, and a native SVG title when visible text is
truncated.

## Independent checks

- Every rendered node label and amount reports `font-size="12"`.
- Expandable income and bucket nodes retain stable keys, `role="button"`,
  `tabindex="0"`, formatted amounts in their accessible names, and Enter/Space
  activation through the same toggle callback as pointer activation.
- Bucket, category, and income-source keys remain distinct and stable, including
  the `HEALTH` bucket key even when its user-facing label is descriptive.
- Exact synthetic bucket/category/refund/deficit values remain present in the
  expanded DOM. Existing rectangle/text pointer handlers remain attached.
- Existing node/link titles remain available, including the full label and
  amount evidence for truncated labels.
- The refund explanation still says that net refund credits are residual after
  same-category offsetting and are not income.
- No Sankey-only category suppression, accounting change, composition redesign,
  or change to unresolved-transfer treatment was introduced.

## Verdict

**PASS.** PI-08 satisfies PI-21 without a frozen-contract revision or a code-only
repair. The implementation preserves identity, values, expansion, pointer and
keyboard interaction, tooltip/title evidence, and exceptional refund/deficit
behavior while materially improving readability. No escalation is required.

## Verification commands

```text
cd frontend && npm test -- --run src/components/finance/charts/SankeyChart-readability-tdd.test.tsx src/components/finance/charts/SankeyChart.test.tsx
```

Result: **7 tests passed**.

```text
cd frontend && npm test -- --run
```

Result: **63 tests passed** across 12 files.

```text
cd frontend && npm run typecheck
cd frontend && npm run build
```

Result: both passed.

```text
python -m pytest tests/test_insights_analytics.py tests/test_cashflow_reporting.py tests/test_sankey_refund_credits.py tests/test_pi19_card_payment_tdd.py tests/test_pi20_card_payment_verifier.py -q
```

Result: **68 tests passed**, with two existing deprecation warnings.

```text
git diff --check
python docs/roadmap/scan.py
```

Result: both passed; roadmap scanner reported **0 issues**.
