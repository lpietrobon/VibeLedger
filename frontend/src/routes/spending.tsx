import { lazy, Suspense, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { SearchBar } from "@/components/finance/SearchBar";
import { AppShell } from "@/components/layout/AppShell";
import { Section } from "@/components/finance/Section";
import { KpiCard } from "@/components/finance/KpiCard";
import { Delta } from "@/components/finance/Delta";
import { CategoryComparison } from "@/components/finance/CategoryComparison";
import { TransactionRow } from "@/components/finance/TransactionRow";
import { AnnotationSheet } from "@/components/finance/AnnotationSheet";
import {
  CATEGORIES,
  getCategoryComparison,
  getCumulativeSpending,
  getSpendingSummary,
  getTransactions,
  patchTransactionAnnotation,
} from "@/lib/api/client";
import type { Transaction } from "@/lib/api/types";
import { formatCurrency } from "@/lib/format";

const CumulativeChart = lazy(() => import("@/components/finance/charts/CumulativeChart"));

const basePath = import.meta.env.BASE_URL.replace(/\/+$/, "");

function appHref(path: string, params?: Record<string, string>) {
  const query = new URLSearchParams(params).toString();
  return `${basePath}${path}${query ? `?${query}` : ""}`;
}

function activePeriodBounds(granularity: "monthly" | "yearly") {
  const today = new Date();
  const year = today.getFullYear();
  const month = String(today.getMonth() + 1).padStart(2, "0");
  const day = String(today.getDate()).padStart(2, "0");
  if (granularity === "yearly") {
    return { startDate: `${year}-01-01`, endDate: `${year}-${month}-${day}` };
  }
  const end = new Date(year, today.getMonth() + 1, 0);
  return {
    startDate: `${year}-${month}-01`,
    endDate: `${year}-${month}-${String(end.getDate()).padStart(2, "0")}`,
  };
}

export default function SpendingPage() {
  const [granularity, setGranularity] = useState<"monthly" | "yearly">("monthly");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All");
  const [selected, setSelected] = useState<Transaction | null>(null);

  const summary = useQuery({
    queryKey: ["spending-summary", granularity],
    queryFn: () => getSpendingSummary({ granularity }),
  });
  const cumulative = useQuery({
    queryKey: ["cumulative", granularity],
    queryFn: () => getCumulativeSpending({ granularity }),
  });
  const comparison = useQuery({ queryKey: ["comparison"], queryFn: getCategoryComparison });
  const tx = useQuery({
    queryKey: ["tx", query, category],
    queryFn: () => getTransactions({ query, category, limit: 30 }),
  });

  const s = summary.data;
  const periodBounds = activePeriodBounds(granularity);

  const handleSave = async (
    id: number,
    payload: Parameters<typeof patchTransactionAnnotation>[1],
  ) => {
    await patchTransactionAnnotation(id, payload);
    tx.refetch();
  };

  return (
    <AppShell>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Spending</h1>
          <p className="text-sm text-muted-foreground">
            {s?.periodLabel ?? "—"} · why the change
          </p>
        </div>
        <div className="inline-flex rounded-md bg-secondary p-0.5 text-sm">
          {(["monthly", "yearly"] as const).map((g) => (
            <button
              key={g}
              onClick={() => setGranularity(g)}
              className={
                "rounded px-3 py-1 text-xs font-medium capitalize transition-colors " +
                (granularity === g
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground")
              }
            >
              {g}
            </button>
          ))}
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {s ? (
          <>
            <KpiCard
              label="Spend"
              value={formatCurrency(s.total, { compact: true })}
              tone="spend"
              sublabel={s.periodLabel}
            />
            <KpiCard
              label="vs previous"
              value={formatCurrency(s.change, { sign: true, compact: true })}
              sublabel={formatCurrency(s.previousTotal, { compact: true }) + " prior"}
              delta={<Delta current={s.total} previous={s.previousTotal} goodDirection="down" />}
            />
            <KpiCard
              label="Projected"
              value={formatCurrency(s.projection, { compact: true })}
              tone="attention"
              sublabel="at current pace"
            />
            <KpiCard
              label="Top driver"
              value={s.topDriver?.category ?? "—"}
              sublabel={
                s.topDriver
                  ? formatCurrency(s.topDriver.amount, { sign: true, compact: true })
                  : "—"
              }
              tone="net"
            />
          </>
        ) : (
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-[86px] animate-pulse rounded-lg bg-secondary" />
          ))
        )}
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Section title="Cumulative spend pace vs last 3 periods">
          <div className="h-64">
            {cumulative.data ? (
              <Suspense fallback={<div className="h-full animate-pulse rounded bg-secondary" />}>
                <CumulativeChart data={cumulative.data} />
              </Suspense>
            ) : (
              <div className="h-full animate-pulse rounded bg-secondary" />
            )}
          </div>
        </Section>

        <Section title="Category change · current vs previous">
          {comparison.data ? (
            <CategoryComparison
              data={comparison.data}
              getCategoryHref={(categoryName) =>
                appHref("/transactions", {
                  category: categoryName,
                  startDate: periodBounds.startDate,
                  endDate: periodBounds.endDate,
                  sort: "date",
                  order: "desc",
                })
              }
            />
          ) : (
            <div className="h-64 animate-pulse rounded bg-secondary" />
          )}
        </Section>
      </div>

      <Section
        title="Transactions"
        className="mt-4"
        action={
          tx.data && tx.data.total > tx.data.items.length ? (
            // This list is a sample, not the set behind the numbers above. Say
            // so rather than letting it read as the whole period.
            <span className="text-xs text-muted-foreground">
              showing {tx.data.items.length} of {tx.data.total}
            </span>
          ) : null
        }
      >
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <SearchBar value={query} onChange={setQuery} placeholder="Search merchant, category…" />
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="h-9 rounded-md border border-input bg-background px-2 text-sm"
          >
            <option value="All">All categories</option>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
        {tx.data ? (
          tx.data.items.length ? (
            <div className="-mx-4 -mb-4">
              {tx.data.items.map((t) => (
                <TransactionRow
                  key={t.id}
                  tx={t}
                  onClick={() => setSelected(t)}
                  selected={selected?.id === t.id}
                />
              ))}
            </div>
          ) : (
            <div className="grid h-24 place-items-center text-sm text-muted-foreground">
              No transactions match those filters.
            </div>
          )
        ) : (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-10 animate-pulse rounded bg-secondary" />
            ))}
          </div>
        )}
      </Section>

      <AnnotationSheet tx={selected} onClose={() => setSelected(null)} onSave={handleSave} />
    </AppShell>
  );
}
