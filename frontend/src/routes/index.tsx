import { useQuery } from "@tanstack/react-query";
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ArrowRight, ChevronRight } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { KpiCard } from "@/components/finance/KpiCard";
import { Delta } from "@/components/finance/Delta";
import { Section } from "@/components/finance/Section";
import { CategoryComparison } from "@/components/finance/CategoryComparison";
import { TransactionRow } from "@/components/finance/TransactionRow";
import {
  getOverviewSummary,
  getCashflowTrend,
  getCategoryComparison,
  getTransactions,
} from "@/lib/api/client";
import { CATEGORY_COLORS } from "@/lib/api/theme";
import { formatCurrency, formatMonth } from "@/lib/format";

const basePath = import.meta.env.BASE_URL.replace(/\/+$/, "");

function appHref(path: string) {
  return `${basePath}${path}`;
}

export default function OverviewPage() {
  const summary = useQuery({ queryKey: ["overview"], queryFn: getOverviewSummary });
  const cashflow = useQuery({ queryKey: ["cashflow"], queryFn: getCashflowTrend });
  const comparison = useQuery({ queryKey: ["comparison"], queryFn: getCategoryComparison });
  const recent = useQuery({
    queryKey: ["recent-tx"],
    queryFn: () => getTransactions({ limit: 8 }),
  });

  const s = summary.data;

  return (
    <AppShell>
      {/* Mobile sticky summary */}
      {s ? (
        <div className="-mx-4 mb-3 flex items-center justify-between border-b border-border bg-background/95 px-4 py-2 md:hidden">
          <div>
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
              Month spend
            </div>
            <div className="text-base font-semibold tabular-nums">
              {formatCurrency(s.monthSpend)}
            </div>
          </div>
          <div className="text-right">
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
              Net cashflow
            </div>
            <div className="text-base font-semibold tabular-nums text-sky-700">
              {formatCurrency(s.netCashflow, { sign: true })}
            </div>
          </div>
        </div>
      ) : null}

      <div className="mb-4 hidden items-end justify-between md:flex">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Overview</h1>
          <p className="text-sm text-muted-foreground">
            As of {s?.asOfDate ?? "—"} · single household
          </p>
        </div>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {summary.isLoading || !s ? (
          Array.from({ length: 4 }).map((_, i) => <KpiSkeleton key={i} />)
        ) : (
          <>
            <KpiCard
              label="Net worth"
              value={formatCurrency(s.netWorth, { compact: true })}
              sublabel={`${formatCurrency(s.assets, { compact: true })} assets · ${formatCurrency(s.liabilities, { compact: true })} debt`}
              tone="net"
            />
            <KpiCard
              label="Month spend"
              value={formatCurrency(s.monthSpend, { compact: true })}
              sublabel={`vs ${formatCurrency(s.previousMonthSpend, { compact: true })} last mo`}
              tone="spend"
              delta={<Delta current={s.monthSpend} previous={s.previousMonthSpend} goodDirection="down" />}
            />
            <KpiCard
              label="Month income"
              value={formatCurrency(s.monthIncome, { compact: true })}
              sublabel={`vs ${formatCurrency(s.previousMonthIncome, { compact: true })} last mo`}
              tone="income"
              delta={<Delta current={s.monthIncome} previous={s.previousMonthIncome} goodDirection="up" />}
            />
            <KpiCard
              label="Net cashflow"
              value={formatCurrency(s.netCashflow, { compact: true, sign: true })}
              sublabel={`vs ${formatCurrency(s.previousNetCashflow, { compact: true, sign: true })} last mo`}
              tone="net"
              delta={<Delta current={s.netCashflow} previous={s.previousNetCashflow} goodDirection="up" />}
            />
          </>
        )}
      </div>

      {/* Charts */}
      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Section title="Cashflow · last 12 months" className="lg:col-span-2">
          <div className="h-64">
            {cashflow.data ? (
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={cashflow.data} margin={{ left: -10, right: 8, top: 8, bottom: 0 }}>
                  <defs>
                    <linearGradient id="netFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#0ea5e9" stopOpacity={0.25} />
                      <stop offset="100%" stopColor="#0ea5e9" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="incomeFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#10b981" stopOpacity={0.22} />
                      <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="spendFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#ef4444" stopOpacity={0.18} />
                      <stop offset="100%" stopColor="#ef4444" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(0 0% 90%)" vertical={false} />
                  <XAxis
                    dataKey="month"
                    tickFormatter={formatMonth}
                    tick={{ fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
                    width={40}
                  />
                  <Tooltip
                    formatter={(v: number) => formatCurrency(v)}
                    labelFormatter={(l: string) => formatMonth(l) + " " + l.slice(0, 4)}
                    contentStyle={{ fontSize: 12, borderRadius: 6 }}
                  />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Area
                    type="monotone"
                    dataKey="income"
                    name="Income"
                    stroke="#10b981"
                    strokeOpacity={0.4}
                    fill="url(#incomeFill)"
                    strokeWidth={1}
                  />
                  <Area
                    type="monotone"
                    dataKey="expenses"
                    name="Spending"
                    stroke="#ef4444"
                    strokeOpacity={0.4}
                    fill="url(#spendFill)"
                    strokeWidth={1}
                  />
                  <Line
                    type="monotone"
                    dataKey="net"
                    name="Net"
                    stroke="#0ea5e9"
                    strokeWidth={2.5}
                    dot={{ r: 2 }}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            ) : (
              <ChartSkeleton />
            )}
          </div>
        </Section>

        <Section title="Needs attention">
          {s ? (
            <ul className="divide-y divide-border">
              <AttentionRow
                label="Unreviewed transactions"
                count={s.needsAttention.unreviewedTransactions}
                filter="unreviewed"
              />
              <AttentionRow
                label="Uncategorized"
                count={s.needsAttention.uncategorizedTransactions}
                filter="uncategorized"
              />
              <AttentionRow
                label="Likely refunds"
                count={s.needsAttention.likelyRefunds}
                filter="refunds"
              />
              <AttentionRow
                label="Transfer pairs pending"
                count={s.needsAttention.transferPairsPending}
                filter="transfers"
              />
            </ul>
          ) : (
            <div className="h-32 animate-pulse rounded bg-secondary" />
          )}
        </Section>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Section
          title="This month vs last month by category"
          action={
            <a
              href={appHref("/spending")}
              className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground"
            >
              Spending detail <ChevronRight className="h-3 w-3" />
            </a>
          }
        >
          {comparison.data ? (
            <CategoryComparison data={comparison.data} />
          ) : (
            <ChartSkeleton />
          )}
        </Section>

        <Section title="Current month by category">
          <div className="h-64">
            {comparison.data ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={[...comparison.data].filter((c) => c.current > 0).sort((a, b) => b.current - a.current)}
                  layout="vertical"
                  margin={{ left: 0, right: 12, top: 4, bottom: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(0 0% 90%)" horizontal={false} />
                  <XAxis
                    type="number"
                    tick={{ fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={(v) => `$${(v / 1000).toFixed(1)}k`}
                  />
                  <YAxis
                    dataKey="category"
                    type="category"
                    tick={{ fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    width={92}
                  />
                  <Tooltip
                    formatter={(v: number) => formatCurrency(v)}
                    contentStyle={{ fontSize: 12, borderRadius: 6 }}
                  />
                  <Bar dataKey="current" radius={[0, 4, 4, 0]}>
                    {comparison.data
                      .filter((c) => c.current > 0)
                      .map((c) => (
                        <Cell key={c.category} fill={CATEGORY_COLORS[c.category] ?? "#64748b"} />
                      ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <ChartSkeleton />
            )}
          </div>
          <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
            {Object.entries(CATEGORY_COLORS).map(([k, v]) => (
              <span key={k} className="inline-flex items-center gap-1">
                <span className="h-2 w-2 rounded-sm" style={{ background: v }} />
                {k}
              </span>
            ))}
          </div>
        </Section>
      </div>

      <Section
        title="Recent transactions"
        className="mt-4"
        action={
          <a
            href={appHref("/transactions")}
            className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground"
          >
            View all <ArrowRight className="h-3 w-3" />
          </a>
        }
      >
        {recent.data ? (
          <div className="-mx-4 -mb-4">
            {recent.data.items.slice(0, 8).map((tx) => (
              <TransactionRow key={tx.id} tx={tx} />
            ))}
          </div>
        ) : (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-10 animate-pulse rounded bg-secondary" />
            ))}
          </div>
        )}
      </Section>
    </AppShell>
  );
}

function AttentionRow({
  label,
  count,
  filter,
}: {
  label: string;
  count: number;
  filter: "unreviewed" | "uncategorized" | "refunds" | "transfers";
}) {
  const dim = count === 0;
  const content = (
    <>
      <span className={dim ? "text-muted-foreground" : "text-foreground"}>{label}</span>
      <span className="flex items-center gap-2">
        <span
          className={
            "min-w-6 rounded px-1.5 py-0.5 text-center text-xs font-semibold tabular-nums " +
            (dim ? "bg-secondary text-muted-foreground" : "bg-amber-50 text-amber-700")
          }
        >
          {count}
        </span>
        <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
      </span>
    </>
  );
  return (
    <li>
      {dim ? (
        <div className="flex items-center justify-between py-2.5 text-sm">{content}</div>
      ) : (
        <a
          href={appHref(`/transactions?filter=${filter}`)}
          className="flex items-center justify-between py-2.5 text-sm hover:text-foreground"
        >
          {content}
        </a>
      )}
    </li>
  );
}

function KpiSkeleton() {
  return <div className="h-[86px] animate-pulse rounded-lg bg-secondary" />;
}
function ChartSkeleton() {
  return <div className="h-full min-h-40 animate-pulse rounded bg-secondary" />;
}
