# The spirit of this epic

A spike is already visible in a spending time series; the frustrating part is needing to leave the chart, reconstruct its dates, and search transaction rows manually to understand it. Make the path from `I see a spike` to `I know why` immediate, numerically honest, and auditable.

The user keeps control of the familiar spending chart. A point on a timeline can reveal a concise annotation and a direct route to the exact transactions underlying that point. A claim like “85% of this $1,000 excess came from insurance” must have a defined, tested baseline and attribution calculation, not an LLM guess or 85% of all spending.

Use the existing ledger, report bounds, Activity drilldown contract, and fully deterministic computation. Prefer correctly abstaining over flagging a routine recurring charge as a surprising anomaly. No Sankey alerts; no separate alarming-first landing page.
