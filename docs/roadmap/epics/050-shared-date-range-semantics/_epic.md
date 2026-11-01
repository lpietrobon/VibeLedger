---
id: 050-shared-date-range-semantics
title: Shared date selection and deterministic comparison semantics
status: planned
owner: null
created: 2026-10-25
revision: 1
---

## Goal

Provide one reusable range-selection model and UI for every applicable date-filtered VibeLedger view, with curated calendar and rolling presets plus explicit custom From–To, and a separate, well-defined comparison rule whose date mapping is deterministic and inspectable.

Read [the spirit](spirit.md) before changing scope.

## Scope and boundaries

- Common required choices: Current month (month-to-date), Current year (year-to-date), Last 30 days, Last 365 days, Custom From–To. Keep custom start and end dates explicit on all date-filtered views; preserve meaningful All-time mode where existing transaction history requires it.
- A selected range is the authoritative inclusive posted-date range for data, charts, KPI aggregates, and transaction drilldowns. Comparison is independent and optional: none, previous calendar month, previous calendar year, or immediately preceding equal-length range. Show both exact ranges; custom selection does not compel comparison.
- Use one typed pure date-domain module, one reusable UI control and backend/request mapping. View-local state remains okay; reuse selection semantics instead of forcing global synchronized state when not desirable.
- Explicitly decide timezone, DST, today inclusion, invalid/unbounded/future ranges, month-end clipping, leap-year handling, unequal-duration comparison disclosure, empty history, and historic/completed windows in TIME-01 before test or implementation.
- Inventory affected views and chart/backend APIs (Overview, Spending, Insights, Transactions/Activity and other date-filtered displays); migrate methodically. Never silently change existing charts' meaning, historical deep-links or accounting.
- Preserve deterministic aggregation and do not alter category rules, transfer accounting, investment tracking, or enable OpenClaw/LLMs.

## Delivery discipline

For each change: accept and freeze independent failing tests (red), implement without weakening the oracle (green), then obtain independent verification using literal fixture expectations. All work is deterministic and uses the existing canonical ledger/evidence semantics. Record commit SHA, actual commands, red/green results, and limitations in each task's append-only Execution Log. Do not mark implementation done merely for passing UI mocks or opening a deep-link. Regenerate `_registry.md` and `_blocked.md` through the roadmap scanner after task changes.

## Revision Log

- rev 1 (2026-10-25): New standalone epic following the spending UX discussion; avoid changing original INSP scope or silently marking previous work complete.
