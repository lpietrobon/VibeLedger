import { lazy, Suspense, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/AppShell";
import { Section } from "@/components/finance/Section";
import { getCashflowSankey, getCategoryMovers, getDailySpend } from "@/lib/api/client";
import { formatMonth } from "@/lib/format";

const SankeyChart = lazy(() => import("@/components/finance/charts/SankeyChart"));
const MoversChart = lazy(() => import("@/components/finance/charts/MoversChart"));
const CalendarHeatmap = lazy(() => import("@/components/finance/charts/CalendarHeatmap"));

const PERIODS = [
  { label: "30d", days: 30 },
  { label: "90d", days: 90 },
  { label: "YTD", days: null },
] as const;

type Period = (typeof PERIODS)[number];

function periodBounds(period: Period) {
  const today = new Date();
  const endDate = today.toISOString().slice(0, 10);
  if (period.days == null) {
    return { startDate: `${today.getFullYear()}-01-01`, endDate };
  }
  const start = new Date(today);
  start.setDate(start.getDate() - (period.days - 1));
  return { startDate: start.toISOString().slice(0, 10), endDate };
}

function monthYearLabel(monthKey: string) {
  return `${formatMonth(monthKey)} ${monthKey.slice(0, 4)}`;
}

export default function InsightsPage() {
  const [period, setPeriod] = useState<Period>(PERIODS[1]);
  const [expandedFlow, setExpandedFlow] = useState<string | null>(null);
  const [year, setYear] = useState<number | undefined>(undefined);

  const bounds = periodBounds(period);
  const sankey = useQuery({
    queryKey: ["cashflow-sankey", bounds.startDate, bounds.endDate],
    queryFn: () => getCashflowSankey(bounds),
  });
  const movers = useQuery({ queryKey: ["category-movers"], queryFn: () => getCategoryMovers() });
  const daily = useQuery({ queryKey: ["daily-spend", year], queryFn: () => getDailySpend({ year }) });

  return (
    <AppShell>
      <div className="mb-4">
        <h1 className="text-xl font-semibold tracking-tight">Insights</h1>
        <p className="text-sm text-muted-foreground">
          Cashflow allocation, month-over-month movers, and daily spending patterns.
        </p>
      </div>

      <Section
        title="Cashflow allocation"
        action={
          <div className="inline-flex rounded-md bg-secondary p-0.5 text-sm">
            {PERIODS.map((p) => (
              <button
                key={p.label}
                type="button"
                onClick={() => {
                  setPeriod(p);
                  setExpandedFlow(null);
                }}
                className={
                  "rounded px-2.5 py-1 text-xs font-medium transition-colors " +
                  (period.label === p.label
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground")
                }
              >
                {p.label}
              </button>
            ))}
          </div>
        }
      >
        {sankey.data ? (
          <Suspense fallback={<div className="h-80 animate-pulse rounded bg-secondary" />}>
            <SankeyChart
              data={sankey.data}
              expanded={expandedFlow}
              onToggle={(key) => setExpandedFlow((cur) => (cur === key ? null : key))}
            />
          </Suspense>
        ) : (
          <div className="h-80 animate-pulse rounded bg-secondary" />
        )}
        <p className="mt-2 text-xs text-muted-foreground">
          Tap Income or a spending bucket to expand its breakdown.
        </p>
      </Section>

      <Section title="Month-over-month movers" className="mt-4">
        {movers.data ? (
          movers.data.items.length ? (
            <>
              <p className="mb-2 text-xs text-muted-foreground">
                {monthYearLabel(movers.data.month)} vs {monthYearLabel(movers.data.previousMonth)} · red means
                spending increased, green means it decreased
              </p>
              <div style={{ height: Math.max(280, 32 * movers.data.items.length + 40) }}>
                <Suspense fallback={<div className="h-full animate-pulse rounded bg-secondary" />}>
                  <MoversChart data={movers.data.items} />
                </Suspense>
              </div>
            </>
          ) : (
            <div className="grid h-24 place-items-center text-sm text-muted-foreground">
              Not enough history to compare months yet.
            </div>
          )
        ) : (
          <div className="h-64 animate-pulse rounded bg-secondary" />
        )}
      </Section>

      <Section
        title="Calendar heatmap"
        className="mt-4"
        action={
          daily.data && daily.data.availableYears.length > 1 ? (
            <select
              value={year ?? daily.data.year}
              onChange={(e) => setYear(Number(e.target.value))}
              className="h-8 rounded-md border border-input bg-background px-2 text-xs"
            >
              {daily.data.availableYears.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
          ) : undefined
        }
      >
        {daily.data ? (
          <Suspense fallback={<div className="h-40 animate-pulse rounded bg-secondary" />}>
            <CalendarHeatmap year={daily.data.year} days={daily.data.days} />
          </Suspense>
        ) : (
          <div className="h-40 animate-pulse rounded bg-secondary" />
        )}
      </Section>
    </AppShell>
  );
}
