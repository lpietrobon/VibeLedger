---
id: SPK-02
epic: 040-timeline-spike-attribution
title: Pin spike detection and attribution with failing backend contract tests
status: todo
dependencies: [SPK-01]
superseded_by: null
assigned_agent: null
created: 2026-10-25
---

## Acceptance Criteria

- [ ] Write a standalone frozen test file (e.g. `tests/test_spk02_timeline_spikes_tdd.py`) that is RED against the current source before anomaly computation changes; record exact failure output and baseline commit in an artifact.
- [ ] Tests assert exact eligible spike bucket IDs, observed amounts, baselines, excess, top driver and attributed percentages using hand-computed values (e.g. $1,200 spent, $200 baseline, $850 attributed => 85% of $1,000 excess).
- [ ] Cover no-spike, recurring-large-charge, sparse/no-history, adjacent peaks, ties, different bucket sizes, leap/month boundaries, refunds, net-negative day, transfers, pending and duplicate-excluded rows.
- [ ] Test attribution invariant: component shares never exceed eligible excess or 100% in total, and residual/offsets are truthful; show counterexamples to naive `largest transaction / excess`.
- [ ] Freeze contract tests for SPK-03; red-to-green must not be achieved by modifying their expected results. Run targeted pytest, record command, seed, version and red failure.

## Technical Context / Test Plan

Suggested role: independent accounting-test author, not SPK-03 implementer. Mock or seed the same canonical ledger semantics used by production aggregation; avoid calling production spike logic to derive expected outputs.

## Execution Log

- 2026-10-25: Task specified from the accepted spending UX priorities. Not started; no failing-test baseline, production implementation, or independent verification claimed.
