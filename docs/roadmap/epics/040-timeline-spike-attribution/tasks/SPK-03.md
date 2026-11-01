---
id: SPK-03
epic: 040-timeline-spike-attribution
title: Implement deterministic timeline spike analysis from canonical ledger
status: todo
dependencies: [SPK-02]
superseded_by: null
assigned_agent: null
created: 2026-10-25
---

## Acceptance Criteria

- [ ] Make the unchanged SPK-02 tests GREEN by adding minimal server-side aggregation/baseline/attribution response shapes; do not duplicate monetary math in the browser.
- [ ] Use the existing posted-spend, confirmed-transfer exclusion, refund netting, duplicate exclusion, and precise inclusive period semantics rather than raw imported signed amounts.
- [ ] Emit stable bucket IDs/dates, observed, baseline, excess, explanation contributions and explicit qualifications or abstention reasons; no fabricated percentages where baseline is unsupported.
- [ ] Bound work to requested/visible timeline dates, use safe resource limits on the single-user Raspberry Pi, and preserve behavior/performance of existing spending APIs.
- [ ] Run targeted and relevant whole-backend pytest; record red/green evidence, commit, schema and any performance measurements. Changes to frozen SPK-02 oracle require escalation.

## Technical Context / Test Plan

Suggested role: backend analytics engineer. Prefer a small reusable analysis helper over framework or LLM integration. Output should support a clearly labeled daily point or cumulative-chart delta without changing Sankey.

## Execution Log

- 2026-10-25: Task specified from the accepted spending UX priorities. Not started; no failing-test baseline, production implementation, or independent verification claimed.
