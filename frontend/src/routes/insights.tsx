import { lazy, Suspense, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/AppShell";
import { Section } from "@/components/finance/Section";
import { DateRangeSelector } from "@/components/finance/DateRangeSelector";
import { getCashflowSankey, getCategoryMovers, getSpendingTimeline } from "@/lib/api/client";
import { initialDateSelection, rangeQuery, validateRange } from "@/lib/dateRange";
import type { DateRangeSelection } from "@/lib/dateRange";

const SankeyChart = lazy(() => import("@/components/finance/charts/SankeyChart"));
const MoversChart = lazy(() => import("@/components/finance/charts/MoversChart"));
const CalendarHeatmap = lazy(() => import("@/components/finance/charts/CalendarHeatmap"));

export default function InsightsPage() {
  const [selectedRange, setSelectedRange] = useState<DateRangeSelection>(() => ({
    ...initialDateSelection("last-30"), comparison: "previous-period",
  }));
  const [expandedFlow, setExpandedFlow] = useState<string | null>(null);
  const valid = validateRange(selectedRange);
  const bounds = { startDate: selectedRange.startDate, endDate: selectedRange.endDate };
  const params = rangeQuery(selectedRange) ?? {};
  const key = [params.startDate, params.endDate, params.compareStartDate, params.compareEndDate];
  const sankey = useQuery({
    queryKey: ["cashflow-sankey", bounds.startDate, bounds.endDate],
    queryFn: () => getCashflowSankey(bounds), enabled: valid,
  });
  const movers = useQuery({
    queryKey: ["category-movers", ...key],
    queryFn: () => getCategoryMovers(params), enabled: valid,
  });
  // Reuse the exact canonical daily expense window rather than a second calendar-year algorithm.
  const daily = useQuery({
    queryKey: ["timeline-days", bounds.startDate, bounds.endDate],
    queryFn: () => getSpendingTimeline(bounds), enabled: valid,
  });
  const years = [...new Set((daily.data?.days ?? []).map((d) => Number(d.date.slice(0, 4))))];

  return (
    <AppShell>
      <div className="mb-4">
        <h1 className="text-xl font-semibold tracking-tight">Insights</h1>
        <p className="text-sm text-muted-foreground">Cashflow allocation, category movers and spending patterns.</p>
      </div>
      <DateRangeSelector value={selectedRange} onChange={(next) => { setSelectedRange(next); setExpandedFlow(null); }} />
      <Section title="Cashflow allocation" className="mt-4">
        {sankey.data ? <Suspense fallback={<div className="h-80 animate-pulse rounded bg-secondary" />}>
          <SankeyChart data={sankey.data} expanded={expandedFlow}
            onToggle={(key) => setExpandedFlow((cur) => cur === key ? null : key)} />
        </Suspense> : <div className="h-80 animate-pulse rounded bg-secondary" />}
        <p className="mt-2 text-xs text-muted-foreground">Tap Income or a spending bucket to expand its breakdown.</p>
        {sankey.isError ? <p role="alert" className="text-xs text-red-600">{sankey.error.message}</p> : null}
      </Section>
      <Section title="Category movers" className="mt-4">
        {movers.data ? movers.data.items.length ? <>
          <p className="mb-2 text-xs text-muted-foreground">
            {selectedRange.startDate} – {selectedRange.endDate}
            {params.compareStartDate ? ` vs ${params.compareStartDate} – ${params.compareEndDate}` : " (no comparison)"}
          </p>
          <div style={{ height: Math.max(280, 32 * movers.data.items.length + 40) }}>
            <Suspense fallback={<div className="h-full animate-pulse rounded bg-secondary" />}>
              <MoversChart data={movers.data.items} />
            </Suspense>
          </div>
        </> : <p className="text-sm text-muted-foreground">No categories for these dates.</p>
          : <div className="h-64 animate-pulse rounded bg-secondary" />}
        {movers.isError ? <p role="alert" className="text-xs text-red-600">{movers.error.message}</p> : null}
      </Section>
      <Section title="Calendar heatmap · selected range" className="mt-4">
        {daily.data ? (
          years.map((year) => <div key={year} className="mb-4">
            <p className="mb-1 text-xs text-muted-foreground">{year}</p>
            <Suspense fallback={<div className="h-40 animate-pulse rounded bg-secondary" />}>
              <CalendarHeatmap year={year} days={daily.data!.days.filter((d) => d.date.startsWith(String(year)))} />
            </Suspense>
          </div>)
        ) : <div className="h-40 animate-pulse rounded bg-secondary" />}
        {daily.isError ? <p role="alert" className="text-xs text-red-600">{daily.error.message}</p> : null}
      </Section>
    </AppShell>
  );
}
