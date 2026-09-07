# Vibe Ledger Finance Intelligence Roadmap

This roadmap tracks the long-running Candor-inspired work. The repository is the durable source of truth; chat is for decisions and coordination.

**2026-09-02 — feature expansion paused.** Current execution is the
[trustworthy cashflow epic](roadmap/epics/010-trustworthy-cashflow/_epic.md), indexed
in [docs/roadmap](roadmap/_registry.md). The ideas and queue below are preserved
as deferred backlog; their earlier priorities do not authorize starting them.
Use the new roadmap's scan and task logs for active work.

## Status vocabulary

- `idea`: captured, not yet committed
- `planned`: scoped and ready to implement
- `in_progress`: actively being worked
- `blocked`: a specific dependency is preventing progress
- `review`: implementation exists and needs verification
- `done`: code, tests, UI/API wiring, and documentation are complete

## Delivery rules

Every feature is split into an independently useful vertical slice:

1. derived-data model and deterministic analyzer
2. API contract
3. tests using synthetic fixtures
4. UI review surface and drill-down
5. privacy review and documentation

Raw transaction data must remain local by default. Any future LLM integration receives a versioned, minimal aggregate/finding payload with evidence references, not raw rows, account identifiers, or free-form merchant descriptions.

## Ranked backlog

| ID | Feature | Value | Effort | Status | Next slice |
|---|---|---:|---:|---|---|
| FI-01 | Recurring intelligence: price changes, missed charges, trials, confidence | Very high | S/M | planned | Extend `recurring_detector.py` with event classifications |
| FI-02 | Cashflow calendar, low-balance forecast, safe-to-spend | Very high | M | idea | Define forecast inputs and uncertainty contract |
| FI-03 | Money-recovery scanner | Very high | S/M | planned | Duplicate/fee/late-refund finding schema |
| FI-04 | Income-integrity monitoring | High | S | idea | Infer cadence and amount bands from normalized income |
| FI-05 | Watchlists and threshold alerts | High | S | planned | Watchlist model plus aggregate endpoint |
| FI-06 | Transaction quality/reconciliation center | High | M | idea | Unified finding types and review states |
| FI-07 | Goals and scenario planner | High | M | idea | Goal model and deterministic projection functions |
| FI-08 | Debt payoff and promotional-rate watchdog | High | M/L | idea | Confirm liability data available from Plaid |
| FI-09 | Local evidence/document ingestion | Medium/high | M/L | idea | Threat model and local OCR spike |
| FI-10 | Benefits, tax, rewards, portfolio-fee analysis | Medium | L | idea | Separate capability designs and external-source policy |

## Deferred execution queue

- [ ] FI-01.1 Specify recurring-event types, confidence, evidence, and suppression rules.
- [ ] FI-01.2 Add synthetic fixtures for price increase, missed recurrence, trial conversion, and duplicate service.
- [ ] FI-01.3 Add API response and a review page with transaction drill-down.
- [ ] FI-01.4 Add privacy contract and update project documentation.

## Feature record template

For each feature, create or append a record containing:

- Problem and user-visible outcome
- Scope and explicit non-goals
- Inputs and derived outputs
- Privacy boundary: what stays local and what may leave the machine
- API/UI contract
- Test plan and acceptance criteria
- Dependencies and risks
- Decision log
- Changelog with commit/PR references

## Definition of done

A feature is not `done` until it has deterministic calculations, synthetic-data tests, an API/UI path, drill-down evidence, privacy documentation, and a recorded verification result. Production financial data may be used only for read-only smoke testing after the synthetic tests pass.

## Checkpoint protocol

At the start of each work session: follow [the active roadmap](roadmap/README.md), inspect git status, and select an eligible task there. Revisit this deferred queue only after an explicit scope decision.

At the end of each session: update status and next action, record tests and unresolved risks, and add a dated note to the project memory. If scope changes, update this roadmap before continuing.
