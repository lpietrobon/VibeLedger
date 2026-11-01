---
id: SPK-05
epic: 040-timeline-spike-attribution
title: Connect timeline annotations and one-action exact-evidence investigation
status: todo
dependencies: [SPK-03, SPK-04]
superseded_by: null
assigned_agent: null
created: 2026-10-25
---

## Acceptance Criteria

- [ ] Render restrained spike indicators on existing temporal charts, a readable tooltip or notes immediately below, and an explicit `Inspect transactions` action that carries the selected point's exact bounds.
- [ ] Make unchanged SPK-04 frontend tests GREEN and preserve original chart comparisons and visual situational awareness; do not add markers to Sankey or category comparison bars.
- [ ] Activity displays the selected date scope and original chart/point context; search/filter remains server-side and paginates to the full posting population, not only initially loaded rows.
- [ ] After drilldown, the signed sum of all underlying eligible transactions reconciles to the point's observed spend, including refunds/transfer/duplicate edge cases.
- [ ] Run frontend tests, typecheck, build and targeted backend tests. Record responsive/keyboard evidence and commit, plus any deliberately unsupported timelines.

## Technical Context / Test Plan

Suggested role: frontend time-series/chart engineer with backend parity review. No LLM calls; preserve incremental delivery: point inspection works before annotation ranking is polished.

## Execution Log

- 2026-10-25: Task specified from the accepted spending UX priorities. Not started; no failing-test baseline, production implementation, or independent verification claimed.
