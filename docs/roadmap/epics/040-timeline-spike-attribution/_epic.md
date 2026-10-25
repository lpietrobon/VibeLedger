---
id: 040-timeline-spike-attribution
title: Timeline spike attribution and direct investigation
status: planned
owner: null
created: 2026-10-25
revision: 1
---

## Goal

Make a spending spike on a timeline immediately explainable: identify unusual spending points, quantify the leading transactions' contribution to the excess against an explicit baseline, and open the exact underlying posted spending evidence with minimal navigation.

Read [the spirit](spirit.md) before changing scope.

## Scope and boundaries

- ONLY temporal spending charts and timelines (including daily buckets and daily increments of a cumulative spending pace chart). Do not implement detection or annotations in Sankey, category composition, Movers bars, or other non-timeline views.
- Existing time-series visualizations and current spending situational-awareness layout remain primary. Avoid a separate alerts landing page or proactive notification system.
- Detection and attribution are server-derived from existing canonical posted-spend accounting; presentation and links must use the same inclusive source point bounds, effective categories, refunds and confirmed-transfer/duplicate exclusions as their evidence.
- Show actual amount, reference/baseline, excess, top attributed transaction/category amount, `X% of spike` when mathematically defensible, and an understandable no-attribution/insufficient-history state. Never equate the full transaction amount with the excess without a defensible attribution rule.
- A chart point should first reveal contextual details and a clear 'Inspect transactions' action. The complete evidence set, not only the first page, must reconcile to that source point.
- Reuse INSP-01's existing drilldown semantics and Activity route patterns; INSP-02/03/04 remain independent Sankey/Movers tasks and are not changed or required as dependencies.
- No LLM, OpenClaw, generic forecasting engine, or redesigned Sankey.

## Delivery discipline

For each change: accept and freeze independent failing tests (red), implement without weakening the oracle (green), then obtain independent verification using literal fixture expectations. All work is deterministic and uses the existing canonical ledger/evidence semantics. Record commit SHA, actual commands, red/green results, and limitations in each task's append-only Execution Log. Do not mark implementation done merely for passing UI mocks or opening a deep-link. Regenerate `_registry.md` and `_blocked.md` through the roadmap scanner after task changes.

## Revision Log

- rev 1 (2026-10-25): New standalone epic following the spending UX discussion; avoid changing original INSP scope or silently marking previous work complete.
