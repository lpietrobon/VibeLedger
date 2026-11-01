---
id: 030-inspectable-aggregates
title: Inspectable aggregates
status: planned
owner: null
created: 2026-09-08
revision: 1
---

## Goal

Let users move directly from an interesting aggregate to the exact Activity rows
that explain it. The first increment covers category summaries, expanded Sankey
categories, and month-over-month movers through deterministic drilldowns, creating
a trustworthy foundation for future intelligence without building a broad LLM
agent. [The spirit of this epic](spirit.md) is the durable statement of intent.

## Scope Notes

- Use a two-step interaction: establish the exact transaction scope, then inspect
  or act on that set in Activity.
- Cover Overview and Spending category comparisons, visible expanded Sankey
  spending categories for the selected Sankey period, and Movers categories for
  the displayed current reporting period.
- Reuse Activity's existing category/date/search filters where they faithfully
  reproduce the aggregate. Introduce only the smallest shared drilldown contract
  needed to prevent URL and accounting semantics from drifting across screens.
- The destination must reproduce the source aggregate's transaction population,
  including posted-spending, confirmed-transfer exclusion, refund treatment,
  effective-category meaning, and inclusive reporting dates. Navigation alone is
  not acceptance evidence.
- Preserve enough source-period context for later comparison inspection, but do not
  add a comparison workspace, generic scope framework, arbitrary chart-point
  selection, conversational agent, or agent infrastructure in this epic.
- If Sankey drilldown truly requires a major chart architecture change, record the
  evidence and narrow the initial interaction rather than forcing a premature
  framework. Current source inspection indicates expanded category nodes and page
  period bounds are already available, so that outcome would require explicit
  justification.

## Revision Log

- rev 1 (2026-09-08): Initial deterministic inspectability scope, grounded in
  `main` after PR #22 was merged.
