---
id: SPK-01
epic: 040-timeline-spike-attribution
title: Inventory time-series evidence and freeze anomaly semantics
status: todo
dependencies: [INSP-01]
superseded_by: null
assigned_agent: null
created: 2026-10-25
---

## Acceptance Criteria

- [ ] Inventory source time-series charts, API endpoints, date buckets, cumulative series, and existing Activity deep-links; record what already works and relevant tests in `artifacts/SPK-01-timeline-contract.md`.
- [ ] Choose and document a deterministic baseline, minimum-history requirements, seasonality/recurring-charge handling, thresholds, null/zero baseline behavior, and point aggregation level; do not label cumulative running total itself a daily anomaly (use increments).
- [ ] Define excess = observed minus baseline for eligible positive spikes and a non-misleading allocation of excess to transactions/categories, including how to cap shares at 100%, handle ties, offsets/refunds, mixed positive/negative components and unexplained residual.
- [ ] Define a stable point identity (inclusive posted dates, bucket/granularity, original report scope, optional comparison), click/tooltip/summary behavior, and evidence parity through INSP-01. Work through small literal numerical examples including an 85%-explained spike.
- [ ] Decide how missing/stale history, zero or negative net spend, empty buckets, and recurring expenses affect the annotation, without silently inventing explanations. Record design decisions and test fixture oracles before implementation.

## Technical Context / Test Plan

Suggested role: accounting/product architect. Inspect `frontend/src/components/finance/charts/CumulativeChart.tsx`, `frontend/src/routes/spending.tsx`, daily-spend endpoints, `app/api/routes.py` and `frontend/src/lib/categoryDrilldown.ts`. Document exact fixture row IDs and signed amounts, not merely a proposed formula.

## Execution Log

- 2026-10-25: Task specified from the accepted spending UX priorities. Not started; no failing-test baseline, production implementation, or independent verification claimed.
