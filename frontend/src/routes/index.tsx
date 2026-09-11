import { lazy, Suspense } from "react";
import { useQuery } from "@tanstack/react-query";
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
import { formatCurrency } from "@/lib/format";
import { categoryDrilldownHref } from "@/lib/categoryDrilldown";

const CashflowChart = lazy(() => import("@/components/finance/charts/CashflowChart"));
const CategoryBarChart = lazy(() => import("@/components/finance/charts/CategoryBarChart"));

const basePath = import.meta.env.BASE_URL.replace(/\/+$/, "");

function appHref(path: string) {
  return `${basePath}${path}`;
}

export default function OverviewPage() {
  const summary = useQuery({ queryKey: ["overview"], queryFn: getOverviewSummary });
  const cashflow = useQuery({ queryKey: ["cashflow"], queryFn: getCashflowTrend });
  const comparison = useQuery({ queryKey: ["comparison"], queryFn: () => getCategoryComparison() });
  const recent = useQuery({
    queryKey: ["recent-tx"],
    queryFn: () => getTransactions({ limit: 8 }),
  });

  const s = summary.data;
  const comparisonAvailable = s?.reporting.comparisonAvailable ?? false;
  const currentPeriod = s?.reporting.currentPeriod;
  const drilldownBounds = currentPeriod?.startDate && currentPeriod.endDate
    ? { startDate: currentPeriod.startDate, endDate: currentPeriod.endDate }
    : null;

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
            Reporting through {s?.asOfDate ?? "—"} · single household
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
              label="Month spend"
              value={formatCurrency(s.monthSpend, { compact: true })}
              sublabel={comparisonAvailable
                ? `vs ${formatCurrency(s.previousMonthSpend, { compact: true })} prior MTD`
                : "No comparable recorded prior period"}
              tone="spend"
              delta={comparisonAvailable ? <Delta current={s.monthSpend} previous={s.previousMonthSpend} goodDirection="down" /> : undefined}
            />
            <KpiCard
              label="Month income"
              value={formatCurrency(s.monthIncome, { compact: true })}
              sublabel={comparisonAvailable
                ? `vs ${formatCurrency(s.previousMonthIncome, { compact: true })} prior MTD`
                : "Recorded posted income"}
              tone="income"
              delta={comparisonAvailable ? <Delta current={s.monthIncome} previous={s.previousMonthIncome} goodDirection="up" /> : undefined}
            />
            <KpiCard
              label="Net cashflow"
              value={formatCurrency(s.netCashflow, { compact: true, sign: true })}
              sublabel={comparisonAvailable
                ? `vs ${formatCurrency(s.previousNetCashflow, { compact: true, sign: true })} prior MTD`
                : "Recorded posted activity"}
              tone="net"
              delta={comparisonAvailable ? <Delta current={s.netCashflow} previous={s.previousNetCashflow} goodDirection="up" /> : undefined}
            />
            <KpiCard
              label="Net worth"
              value={formatCurrency(s.netWorth, { compact: true })}
              sublabel={`${formatCurrency(s.assets, { compact: true })} assets · ${formatCurrency(s.liabilities, { compact: true })} debt`}
              tone="net"
            />
          </>
        )}
      </div>

      {summary.isError ? (
        <p role="alert" className="mt-3 text-sm text-red-600">Could not load the spending summary: {summary.error.message}</p>
      ) : s ? (
        <p className="mt-2 text-xs text-muted-foreground">
          {s.reporting.comparisonQualification}
          {s.needsAttention.transferPairsPending > 0 ? " Possible transfers remain counted until reviewed." : ""}
        </p>
      ) : null}

      {/* Charts */}
      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Section title="Cashflow · last 12 months" className="lg:col-span-2">
          <div className="h-64">
            {cashflow.isError ? (
              <p role="alert" className="grid h-full place-items-center text-sm text-red-600">Could not load cashflow: {cashflow.error.message}</p>
            ) : cashflow.data ? (
              <Suspense fallback={<ChartSkeleton />}>
                <CashflowChart data={cashflow.data} />
              </Suspense>
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
                href="/transfers"
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
          {comparison.isError ? (
            <p role="alert" className="grid h-40 place-items-center text-sm text-red-600">Could not load category comparison: {comparison.error.message}</p>
          ) : comparison.data ? (
            <CategoryComparison
              data={comparison.data}
              currentLabel="This month to date"
              previousLabel="Prior comparable period"
              getCategoryHref={drilldownBounds
                ? (category) => categoryDrilldownHref({ category, ...drilldownBounds })
                : undefined}
            />
          ) : (
            <ChartSkeleton />
          )}
        </Section>

        <Section title="Current month by category">
          <div className="h-64">
            {comparison.isError ? (
              <p role="alert" className="grid h-full place-items-center text-sm text-red-600">Category chart unavailable.</p>
            ) : comparison.data ? (
              <Suspense fallback={<ChartSkeleton />}>
                <CategoryBarChart data={comparison.data} />
              </Suspense>
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
  href,
}: {
  label: string;
  count: number;
  /** Drill-down on the Transactions screen; the server-side query lives there. */
  filter?: "unreviewed" | "uncategorized" | "refunds";
  /** Somewhere other than Transactions — pending pairs belong on Transfers. */
  href?: string;
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
          href={appHref(href ?? `/transactions?filter=${filter}`)}
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
