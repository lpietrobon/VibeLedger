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
import { useAccountScope, useAccountScopeQuery } from "@/lib/accountScope";

const CashflowChart = lazy(() => import("@/components/finance/charts/CashflowChart"));
const CategoryBarChart = lazy(() => import("@/components/finance/charts/CategoryBarChart"));

const basePath = import.meta.env.BASE_URL.replace(/\/+$/, "");

function appHref(path: string) {
  return `${basePath}${path}`;
}

export default function OverviewPage() {
  const [accountIds] = useAccountScope();
  const summary = useQuery({
    queryKey: ["overview", accountIds],
    queryFn: () => getOverviewSummary({ accountIds }),
  });
  const cashflow = useQuery({
    queryKey: ["cashflow", accountIds],
    queryFn: () => getCashflowTrend({ accountIds }),
  });
  const comparison = useQuery({
    queryKey: ["comparison", accountIds],
    queryFn: () => getCategoryComparison({ accountIds }),
  });
  const accountScopeQuery = useAccountScopeQuery();
  const recent = useQuery({
    queryKey: ["recent-tx", accountScopeQuery],
    queryFn: () => getTransactions({ query: accountScopeQuery, limit: 8 }),
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
          {comparison.data ? (
            <CategoryComparison data={comparison.data} />
          ) : (
            <ChartSkeleton />
          )}
        </Section>

        <Section title="Current month by category">
          <div className="h-64">
            {comparison.data ? (
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
