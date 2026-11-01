# Spending UX priorities — planning addendum (2026-10-25)

Status: proposal for roadmap decomposition; **not** an implementation task or a claim of delivery.

## User problem and priority

The Spending view is the default place to establish situational awareness. Preserve fast deterministic monthly/yearly and rolling comparisons. The largest current friction is the journey from noticing a spike in a chart to discovering the transactions responsible. Prioritize spike attribution and a direct evidence path, followed closely by shared period-selection logic.

## A. Spike → explanation → transactions (first priority)

- Detect unusually high points at the chart's actual aggregation level using an explainable deterministic baseline; avoid classifying ordinary scheduled/periodic payment behavior as extraordinary without context.
- Make points inspectable; preserve chart tap/selection behavior, then provide a deliberate action to open the precise underlying transaction set (rather than surprising navigation on first tap).
- Attribute an excess over an explicit baseline to concrete transactions and/or categories. State amounts and the proportion explained by the leading contribution when mathematically valid. Example: “85% of the $1,000 excess is attributable to a $850 insurance payment.” Do **not** divide a transaction's full amount by the excess if that would produce a misleading percentage; define the contribution method, handle negative/refund contributions and residuals, and show the baseline.
- Tooltip or concise notes below the chart should surface the date, observed spending, reference/baseline, main driver and quantified contribution; exact corresponding transactions must be accessible from the explanation.
- Drilldowns must use the existing INSP-01 contract and preserve inclusive posted-date, effective-category, transfer and refund semantics. Verify that selected transactions reconcile to the source point, not just that a URL opens.
- Start with existing spending charts, not a separate anomaly dashboard or LLM service.

**Existing work to reuse:** epic `030-inspectable-aggregates` spirit and `INSP-01` shared evidence contract; check `INSP-02` (Sankey), `INSP-03` (Movers), `INSP-04` (independent parity verification) before new implementation. INSP-01 is marked done; INSP-02/03/04 were todo in the branch's generated registry. This is a material extension of epic 030's initial scope, which explicitly excluded arbitrary chart-point selection: revise the epic scope/revision log **when** tasks are decomposed; do not silently treat this note as such a revision.

## B. Unified range and comparison semantics (second priority)

- One reusable date-selection experience on every date-filtered relevant view: **Current month, Current year, Last 30 days, Last 365 days, Custom From–To**.
- The selected inclusive From–To range is always explicit and authoritative across relevant charts, KPI totals, and transaction evidence.
- Comparison is a separate optional rule, chosen by the user (e.g., none, previous month, previous year, immediately preceding equal-duration period). Translate the selected dates deterministically; example October 5–15 vs September 5–15 for previous month. Display actual resulting bounds.
- Specify edge-case policies before implementation: month-end clipping, leap years, inclusive day counts, incomplete/current periods, time zone and posting-date alignment, missing history, and future dates.
- Share the date arithmetic, range labels, typed selector and backend request contract. Keep page-local selection where appropriate; don't duplicate period math. A custom date range need not imply a comparison.
- Audit existing implementations before replacing them: Spending currently has monthly/yearly plus Calendar/Rolling comparison (30/365 days); Insights has 30/90/YTD. Preserve working behavior or explicitly justify any preset changes.

## Work sequencing / governance

1. Inventory affected charts, API endpoints, and current date math; map any already-complete tasks to avoid duplicate work.
2. Define failing contract tests (date-boundary mapping, chart/filter parity, anomalous excess/contribution calculations).
3. Implement incremental chart UX and shared selectors, then obtain independent verification of accounting/evidence parity.
4. Create the formal epic/tasks with dependencies, acceptance criteria and append-only execution logs. Respect existing `docs/roadmap/README.md` convention: **do not hand-edit generated `_registry.md` or `_blocked.md`**; run `python docs/roadmap/scan.py` after task changes and before committing the formally scheduled roadmap.

Non-goals: LLM/OpenClaw integration, general-purpose agent, arbitrary configurable rolling-duration presets, changing deterministic categorization, investment tracking within these spending tasks.

## Decomposition update (2026-10-25)

The proposed objectives are now execution tasks in separate epics:
[040 timeline spike attribution](epics/040-timeline-spike-attribution/_epic.md)
(**time-series charts only; no Sankey spikes**) and
[050 shared date range semantics](epics/050-shared-date-range-semantics/_epic.md).
Each epic separates red-test contract, implementation and independent verification;
this document remains historical product context, not an execution task.
