import { lazy, Suspense, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/AppShell";
import { Section } from "@/components/finance/Section";
import { AnnotationSheet } from "@/components/finance/AnnotationSheet";
import { SearchBar } from "@/components/finance/SearchBar";
import { TransactionRow } from "@/components/finance/TransactionRow";
import { CategoryComparison } from "@/components/finance/CategoryComparison";
import { DateRangeSelector } from "@/components/finance/DateRangeSelector";
import { PriorPeriodsControl } from "@/components/finance/PriorPeriodsControl";
import { comparisonPeriods, initialDateSelection, rangeQuery, validateRange } from "@/lib/dateRange";
import type { DateRangeSelection } from "@/lib/dateRange";
import type { DateWindowParams } from "@/lib/api/client";
import {
  CATEGORIES, getCategoryComparisonPeriod, getCumulativeSpending, getSpendingSummary,
  getSpendingTimeline, getSpendingDay, getTransactions, patchTransactionAnnotation,
} from "@/lib/api/client";
import type { Transaction } from "@/lib/api/types";
import { formatCurrency } from "@/lib/format";
import { invalidateLedger } from "@/lib/api/cache";
import { categoryDrilldownHref } from "@/lib/categoryDrilldown";

const CumulativeChart = lazy(() => import("@/components/finance/charts/CumulativeChart"));
const basePath = import.meta.env.BASE_URL.replace(/\/+$/, "");

function CompactMetric({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="min-w-0 rounded-lg border border-border bg-card px-1.5 py-2 sm:px-3">
      <div className="truncate text-[10px] font-medium text-muted-foreground sm:text-xs">{label}</div>
      <div title={value} className="mt-1 truncate text-sm font-semibold tabular-nums sm:text-xl">{value}</div>
      <div className="mt-1 truncate text-[10px] text-muted-foreground" title={note}>{note}</div>
    </div>
  );
}

export default function SpendingPage() {
  const queryClient = useQueryClient();
  const [selectedRange, setSelectedRange] = useState<DateRangeSelection>(() => ({
    ...initialDateSelection("current-month"), comparison: "previous-month",
  }));
  const [priorCount, setPriorCount] = useState(2);
  const [selectedPoint, setSelectedPoint] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All");
  const [selected, setSelected] = useState<Transaction | null>(null);
  const valid = validateRange(selectedRange);
  const granularity = selectedRange.preset === "current-year" || selectedRange.preset === "last-365" ? "yearly" : "monthly";
  const params: DateWindowParams = rangeQuery(selectedRange) ?? {};
  const dataKey = [params.startDate, params.endDate, params.compareStartDate, params.compareEndDate];
  const historic = valid ? comparisonPeriods(selectedRange, priorCount) : [];
  const summary = useQuery({
    queryKey: ["spending-summary", granularity, ...dataKey],
    queryFn: () => getSpendingSummary({ granularity, ...params }),
    enabled: valid,
  });
  const cumulative = useQuery({
    queryKey: ["cumulative", granularity, priorCount, ...dataKey],
    queryFn: () => getCumulativeSpending({
      granularity, ...params, comparisonPeriods: historic,
      // 0 historical lines does NOT remove the always-on KPI comparison.
      compareStartDate: priorCount ? params.compareStartDate : undefined,
      compareEndDate: priorCount ? params.compareEndDate : undefined,
    }),
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
  // Default to the most recent flagged peak or latest spending day. Any chart date
  // can override this; selection never requires a detector to call the drill-down.
  const activeDate = selectedPoint ??
    (timeline.data?.spikes?.[0]?.date ??
      timeline.data?.days.slice().reverse().find((day) => day.amount !== 0)?.date ?? null);
  const day = useQuery({
    queryKey: ["spending-day", activeDate],
    queryFn: () => getSpendingDay(activeDate!),
    enabled: valid && Boolean(activeDate),
  });
  const tx = useQuery({
    queryKey: ["tx", query, category, selectedRange.startDate, selectedRange.endDate],
    queryFn: () => getTransactions({
      query: query ? "is:spend " + query : "is:spend",
      category, startDate: selectedRange.startDate, endDate: selectedRange.endDate, limit: 30,
    }),
    enabled: valid,
  });
  const s = summary.data;
  const topCategory = comparison.data?.items.find((item) => item.current > 0);
  const handleSave = async (id: number, payload: Parameters<typeof patchTransactionAnnotation>[1]) => {
    await patchTransactionAnnotation(id, payload);
    await invalidateLedger(queryClient);
  };
  const detailHref = (date: string) =>
    basePath + "/transactions?source=timeline&startDate=" + date + "&endDate=" + date +
      "&query=is%3Aspend&sort=amount&order=desc";

  return (
    <AppShell>
      <div className="mb-2 flex items-start justify-between gap-3">
        <h1 className="text-xl font-semibold tracking-tight">Spending</h1>
        <p className="max-w-40 text-right text-[11px] leading-tight text-muted-foreground">
          Spending pace and comparisons
        </p>
      </div>
      <DateRangeSelector value={selectedRange} onChange={(v) => { setSelectedRange(v); setSelectedPoint(null); }} />
      <div className="mt-2 grid grid-cols-4 gap-1.5 sm:gap-2">
        {s ? <>
          <CompactMetric label="Spend" value={formatCurrency(s.total, { compact: true })} note="Selected period" />
          <CompactMetric label="vs prior" value={s.reporting.comparisonAvailable && s.changePct !== null
            ? (s.changePct > 0 ? "+" : "") + s.changePct + "%"
            : "—"}
            note={s.reporting.comparisonAvailable && s.change !== null
              ? formatCurrency(s.change, { sign: true, compact: true }) : "Not available"} />
          <CompactMetric label="Top category" value={topCategory?.category ?? "—"}
            note={topCategory ? formatCurrency(topCategory.current, { compact: true }) : "No spending"} />
          <CompactMetric label="Daily avg" value={s.dailyAverage == null ? "—" : formatCurrency(s.dailyAverage, { compact: true })}
            note="Per selected day" />
        </> : Array.from({ length: 4 }, (_, i) =>
          <div key={i} className="h-16 animate-pulse rounded-lg bg-secondary" />)}
      </div>
      {summary.isError ? <p role="alert" className="mt-2 text-sm text-red-600">{summary.error.message}</p> : null}
      <Section title="Cumulative spending" className="mt-3"
        action={<PriorPeriodsControl value={priorCount} onChange={setPriorCount} />}>
        <div className="h-52 sm:h-64">
          {cumulative.data && timeline.data ? <Suspense fallback={<div className="h-full animate-pulse rounded bg-secondary" />}>
            <CumulativeChart data={cumulative.data} days={timeline.data.days} spikes={timeline.data.spikes}
              selectedDate={activeDate} priorCount={priorCount} onSelect={setSelectedPoint} />
          </Suspense> : <div className="h-full animate-pulse rounded bg-secondary" />}
        </div>
        {cumulative.isError || timeline.isError ? <p role="alert" className="text-xs text-red-600">Unable to load spending chart.</p> : null}
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-muted-foreground">
          <span><span className="mr-1 inline-block h-0.5 w-3 bg-blue-600 align-middle" />Current period</span>
          {historic.map((window, i) => (
            <span key={window.startDate}>
              <span className="mr-1 inline-block h-0.5 w-3 align-middle"
                style={{ backgroundColor: ["#6b7280", "#9ca3af", "#d1d5db"][i] }} />
              {window.startDate} – {window.endDate}
            </span>
          ))}
        </div>
      </Section>

      <Section title={activeDate ? activeDate + " · top five transactions" : "Select a day"}
        className="mt-3">
        {day.data && activeDate ? <>
          <div className="mb-2 flex items-center justify-between text-xs">
            <span className="text-muted-foreground">{day.data.transaction_count} posted spending entries</span>
            <span className="font-semibold">{formatCurrency(day.data.total)} net that day</span>
          </div>
          <div className="w-full overflow-x-auto">
            <table className="w-full table-fixed text-xs">
              <thead className="text-left text-[10px] text-muted-foreground">
                <tr>
                  <th className="w-[22%] py-1">Amount</th>
                  <th className="w-[38%] py-1">Merchant</th>
                  <th className="w-[20%] py-1 text-right">% day</th>
                  <th className="w-[20%] py-1 text-right">Cum %</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {day.data.items.map((item) =>
                  <tr key={item.id}>
                    <td className="py-2 font-medium tabular-nums">{formatCurrency(item.amount, { compact: true })}</td>
                    <td className="truncate py-2" title={item.merchant}>{item.merchant}</td>
                    <td className="py-2 text-right tabular-nums">
                      {item.percent_of_day === null ? "—" : item.percent_of_day + "%"}
                    </td>
                    <td className="py-2 text-right tabular-nums">
                      {item.cumulative_percent === null ? "—" : item.cumulative_percent + "%"}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          {day.data.items.some((row) => (row.percent_of_day !== null && row.percent_of_day > 100) || (row.cumulative_percent !== null && row.cumulative_percent > 100))
            ? <p className="mt-1 text-[10px] text-muted-foreground">Refund offsets can make shares exceed 100% of net spending.</p> : null}
          {day.data.transaction_count === 0 ? <p className="py-2 text-xs text-muted-foreground">No spending transactions for this day.</p> : null}
          <a href={detailHref(activeDate)} className="mt-2 inline-block text-xs font-semibold text-primary underline">
            Inspect all transactions for this day
          </a>
        </> : day.isError ? <p role="alert" className="text-xs text-red-600">Could not load the selected day.</p>
          : <p className="text-xs text-muted-foreground">{activeDate ? "Loading transactions…" : "Tap any point on the chart."}</p>}
      </Section>

      <Section title="Spending by category" className="mt-4">
        {comparison.data ? <CategoryComparison data={comparison.data.items}
          currentLabel={selectedRange.startDate + " – " + selectedRange.endDate}
          previousLabel={params.compareStartDate ? params.compareStartDate + " – " + params.compareEndDate : "No comparison"}
          showPrevious={Boolean(params.compareStartDate)}
          getCategoryHref={(name) => categoryDrilldownHref({
            category: name, startDate: selectedRange.startDate, endDate: selectedRange.endDate,
          })} /> : <div className="h-40 animate-pulse rounded bg-secondary" />}
      </Section>
      <Section title="Spending transactions" className="mt-4">
        <div className="mb-3 flex flex-wrap gap-2">
          <SearchBar value={query} onChange={setQuery} placeholder="Search merchant, category…" />
          <select value={category} onChange={(e) => setCategory(e.target.value)}
            className="h-9 rounded-md border border-input bg-background px-2 text-sm">
            <option value="All">All categories</option>
            {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        {tx.data ? <div className="-mx-4 -mb-4">
          {tx.data.items.map((t) =>
            <TransactionRow key={t.id} tx={t} onClick={() => setSelected(t)} selected={selected?.id === t.id} />)}
        </div> : <div className="h-24 animate-pulse rounded bg-secondary" />}
      </Section>
      <AnnotationSheet tx={selected} onClose={() => setSelected(null)} onSave={handleSave} />
    </AppShell>
  );
}
