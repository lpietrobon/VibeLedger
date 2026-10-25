import { lazy, Suspense, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/AppShell";
import { Section } from "@/components/finance/Section";
import { KpiCard } from "@/components/finance/KpiCard";
import { Delta } from "@/components/finance/Delta";
import { CategoryComparison } from "@/components/finance/CategoryComparison";
import { TransactionRow } from "@/components/finance/TransactionRow";
import { AnnotationSheet } from "@/components/finance/AnnotationSheet";
import { SearchBar } from "@/components/finance/SearchBar";
import { DateRangeSelector } from "@/components/finance/DateRangeSelector";
import { SpendingTimelineChart } from "@/components/finance/charts/SpendingTimelineChart";
import { initialDateSelection, rangeQuery, validateRange } from "@/lib/dateRange";
import type { DateRangeSelection } from "@/lib/dateRange";
import type { DateWindowParams } from "@/lib/api/client";
import {
  CATEGORIES, getCategoryComparisonPeriod, getCumulativeSpending, getSpendingSummary,
  getSpendingTimeline, getTransactions, patchTransactionAnnotation,
} from "@/lib/api/client";
import type { Transaction } from "@/lib/api/types";
import { formatCurrency } from "@/lib/format";
import { invalidateLedger } from "@/lib/api/cache";
import { categoryDrilldownHref } from "@/lib/categoryDrilldown";

const CumulativeChart = lazy(() => import("@/components/finance/charts/CumulativeChart"));
const basePath = import.meta.env.BASE_URL.replace(/\/+$/, "");

export default function SpendingPage() {
  const queryClient = useQueryClient();
  const [selectedRange, setSelectedRange] = useState<DateRangeSelection>(() => ({
    ...initialDateSelection("current-month"), comparison: "previous-month",
  }));
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All");
  const [selected, setSelected] = useState<Transaction | null>(null);
  const [selectedPoint, setSelectedPoint] = useState<string | null>(null);
  const valid = validateRange(selectedRange);
  const granularity = selectedRange.preset === "current-year" || selectedRange.preset === "last-365" ? "yearly" : "monthly";
  const dates = rangeQuery(selectedRange);
  const params: DateWindowParams = dates ?? {};
  const dataKey = [params.startDate, params.endDate, params.compareStartDate, params.compareEndDate];
  const summary = useQuery({
    queryKey: ["spending-summary", granularity, ...dataKey],
    queryFn: () => getSpendingSummary({ granularity, ...params }),
    enabled: valid,
  });
  const cumulative = useQuery({
    queryKey: ["cumulative", granularity, ...dataKey],
    queryFn: () => getCumulativeSpending({ granularity, ...params }),
    enabled: valid,
  });
  const comparison = useQuery({
    queryKey: ["category-comparison", granularity, ...dataKey],
    queryFn: () => getCategoryComparisonPeriod(granularity, "calendar", params),
    enabled: valid,
  });
  const timeline = useQuery({
    queryKey: ["spending-timeline", selectedRange.startDate, selectedRange.endDate],
    queryFn: () => getSpendingTimeline({ startDate: selectedRange.startDate, endDate: selectedRange.endDate }),
    enabled: valid,
  });
  const tx = useQuery({
    queryKey: ["tx", query, category, selectedRange.startDate, selectedRange.endDate],
    queryFn: () => getTransactions({
      query: query ? `is:spend ${query}` : "is:spend",
      category, startDate: selectedRange.startDate, endDate: selectedRange.endDate, limit: 30,
    }),
    enabled: valid,
  });
  const s = summary.data;
  const selectedSpike = timeline.data?.spikes.find((spike) => spike.date === selectedPoint);
  const highlights = [...(timeline.data?.spikes ?? [])].sort((a, b) => b.excess - a.excess).slice(0, 4);
  const handleSave = async (id: number, payload: Parameters<typeof patchTransactionAnnotation>[1]) => {
    await patchTransactionAnnotation(id, payload);
    await invalidateLedger(queryClient);
  };
  const detailHref = (date: string) => `${basePath}/transactions?source=timeline&startDate=${date}&endDate=${date}&query=is:spend`;

  return (
    <AppShell>
      <div className="mb-4">
        <h1 className="text-xl font-semibold tracking-tight">Spending</h1>
        <p className="text-sm text-muted-foreground">Spending pace, comparisons and the transactions behind them.</p>
      </div>
      <DateRangeSelector value={selectedRange} onChange={(v) => { setSelectedRange(v); setSelectedPoint(null); }} />
      <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
        {s ? <>
          <KpiCard label="Spend" value={formatCurrency(s.total, { compact: true })} sublabel={s.periodLabel} tone="spend" />
          <KpiCard label="vs selected comparison" value={s.reporting.comparisonAvailable && s.change !== null
              ? formatCurrency(s.change, { sign: true, compact: true }) : "—"}
              sublabel={s.reporting.comparisonAvailable
                ? `${formatCurrency(s.previousTotal, { compact: true })} prior` : "No comparable recorded period"}
              delta={s.reporting.comparisonAvailable
                ? <Delta current={s.total} previous={s.previousTotal} goodDirection="down" /> : undefined} />
          <KpiCard label="Selected range total" value={formatCurrency(s.total, { compact: true })} tone="attention"
            sublabel="Recorded posted spending" />
          <KpiCard label="Top change driver" value={s.topDriver?.category ?? "—"}
            sublabel={s.topDriver ? formatCurrency(s.topDriver.amount, { sign: true, compact: true }) : "No comparable history"} tone="net" />
        </> : Array.from({ length: 4 }, (_, i) => <div key={i} className="h-[86px] animate-pulse rounded-lg bg-secondary" />)}
      </div>
      {summary.isError ? <p role="alert" className="mt-2 text-sm text-red-600">{summary.error.message}</p> : null}
      {s ? <p className="mt-2 text-xs text-muted-foreground">{s.reporting.comparisonQualification}</p> : null}
      <Section title="Daily spending · investigate peaks" className="mt-4">
        {timeline.isError ? <p role="alert" className="text-sm text-red-600">Could not load daily spending.</p> : null}
        {timeline.data ? <>
          {timeline.data.days.length > 0
            ? <div className="h-60"><SpendingTimelineChart days={timeline.data.days} spikes={timeline.data.spikes} onSelect={setSelectedPoint} /></div>
            : <p className="text-xs text-muted-foreground">No daily points in this range.</p>}
          {selectedPoint ? (
            <div className="mt-2 rounded-md bg-secondary p-3 text-sm" aria-live="polite">
              <div className="font-semibold">{selectedPoint}</div>
              {selectedSpike ? <>
                <p>Spending {formatCurrency(selectedSpike.observed)}, baseline {formatCurrency(selectedSpike.baseline)}; excess {formatCurrency(selectedSpike.excess)}.</p>
                <p>{selectedSpike.top_merchant} ({formatCurrency(selectedSpike.top_amount ?? 0)}) could explain up to
                  {" "}{selectedSpike.max_attributable_pct}% of this excess.</p>
              </> : <p>Selected daily spend: {formatCurrency(timeline.data.days.find((d) => d.date === selectedPoint)?.amount ?? 0)}.</p>}
              <a href={detailHref(selectedPoint)} className="mt-2 inline-block font-semibold text-sky-700 underline">Inspect transactions for this day</a>
            </div>
          ) : null}
          {highlights.length ? <div className="mt-3 space-y-2">
            <p className="text-xs font-medium text-muted-foreground">Unusual peaks · select a point on the chart or below</p>
            {highlights.map((spike) => (
              <div key={spike.date} className="flex flex-wrap items-center justify-between gap-2 text-xs">
                <button type="button" onClick={() => setSelectedPoint(spike.date)} className="text-left font-medium text-sky-700 underline">
                  {spike.date}: {formatCurrency(spike.excess)} above baseline
                </button>
                <span>{spike.top_merchant} · up to {spike.max_attributable_pct}%</span>
              </div>
            ))}
          </div> : <p className="mt-2 text-xs text-muted-foreground">No reliably detected unusual peaks for this selected period.</p>}
          <p className="mt-2 text-xs text-muted-foreground">Spike labels are deterministic estimates from recorded activity, not causal proof. Coverage may be incomplete.</p>
        </> : <div className="h-60 animate-pulse rounded bg-secondary" />}
      </Section>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Section title="Cumulative spend pace vs selected comparison">
          <div className="h-64">
            {cumulative.data ? <Suspense fallback={<div className="h-full animate-pulse rounded bg-secondary" />}>
              <CumulativeChart data={cumulative.data} />
            </Suspense> : <div className="h-full animate-pulse rounded bg-secondary" />}
          </div>
        </Section>
        <Section title="Category spending · selected periods">
          {comparison.data ? <>
            <CategoryComparison data={comparison.data.items} currentLabel={selectedRange.startDate + " – " + selectedRange.endDate}
              previousLabel={params.compareStartDate ? params.compareStartDate + " – " + params.compareEndDate : "No comparison"}
              showPrevious={Boolean(params.compareStartDate)}
              getCategoryHref={(name) => categoryDrilldownHref({ category: name,
                startDate: selectedRange.startDate, endDate: selectedRange.endDate })} />
          </> : <div className="h-64 animate-pulse rounded bg-secondary" />}
          {comparison.isError ? <p role="alert" className="text-xs text-red-600">{comparison.error.message}</p> : null}
        </Section>
      </div>
      <Section title="Spending transactions" className="mt-4">
        {tx.data ? <p className="mb-2 text-xs text-muted-foreground">Showing {tx.data.items.length} of {tx.data.total} posted spending transactions in this range.</p> : null}
        <div className="mb-3 flex flex-wrap gap-2">
          <SearchBar value={query} onChange={setQuery} placeholder="Search merchant, category…" />
          <select value={category} onChange={(e) => setCategory(e.target.value)}
            className="h-9 rounded-md border border-input bg-background px-2 text-sm">
            <option value="All">All categories</option>
            {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        {tx.isError ? <p role="alert" className="text-sm text-red-600">{tx.error.message}</p> : null}
        {tx.data ? <div className="-mx-4 -mb-4">
          {tx.data.items.map((t) => <TransactionRow key={t.id} tx={t} onClick={() => setSelected(t)} selected={selected?.id === t.id} />)}
        </div> : <div className="h-32 animate-pulse rounded bg-secondary" />}
      </Section>
      <AnnotationSheet tx={selected} onClose={() => setSelected(null)} onSave={handleSave} />
    </AppShell>
  );
}
