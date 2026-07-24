import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { Section } from "@/components/finance/Section";
import { KpiCard } from "@/components/finance/KpiCard";
import { getRecurring } from "@/lib/api/client";
import { formatCurrency, formatDate } from "@/lib/format";

type StatusFilter = "active" | "all" | "inactive";

const CADENCE_LABEL: Record<string, string> = {
  weekly: "Weekly",
  biweekly: "Every 2 weeks",
  monthly: "Monthly",
  quarterly: "Quarterly",
  yearly: "Yearly",
};

export default function RecurringPage() {
  const [status, setStatus] = useState<StatusFilter>("active");

  const recurring = useQuery({
    queryKey: ["recurring", status],
    queryFn: () => getRecurring(status === "all" ? {} : { status }),
  });

  const items = recurring.data?.items ?? [];
  const summary = recurring.data?.summary;

  return (
    <AppShell>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Subscriptions & recurring</h1>
          <p className="text-sm text-muted-foreground">
            Merchants billed on a regular cadence, inferred from your history.
          </p>
        </div>
        <div className="inline-flex rounded-md bg-secondary p-0.5 text-sm">
          {(["active", "all", "inactive"] as const).map((s) => (
            <button
              key={s}
              onClick={() => setStatus(s)}
              className={
                "rounded px-3 py-1 text-xs font-medium capitalize transition-colors " +
                (status === s ? "bg-background text-foreground shadow-sm" : "text-muted-foreground")
              }
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <KpiCard label="Active" value={`${summary?.active_count ?? 0}`} tone="net" />
        <KpiCard
          label="Est. monthly"
          value={formatCurrency(summary?.active_monthly_estimate ?? 0, { compact: true })}
          tone="spend"
        />
        <KpiCard
          label="Est. annual"
          value={formatCurrency(summary?.active_annual_estimate ?? 0, { compact: true })}
          tone="attention"
        />
      </div>

      <Section title="Detected series" className="mt-4">
        {/* Desktop table */}
        <div className="hidden md:block">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-[11px] uppercase tracking-wide text-muted-foreground">
                <th className="py-2 font-medium">Merchant</th>
                <th className="py-2 font-medium">Cadence</th>
                <th className="py-2 text-right font-medium">Avg</th>
                <th className="py-2 text-right font-medium">Monthly</th>
                <th className="py-2 font-medium">Next</th>
                <th className="py-2 text-right font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {items.map((series) => (
                <tr key={series.merchant_key} className="border-b border-border">
                  <td className="py-2 font-medium">
                    {series.merchant_label}
                    {!series.amount_consistent ? (
                      <span className="ml-2 rounded bg-secondary px-1 py-0.5 text-[10px] text-muted-foreground">
                        variable
                      </span>
                    ) : null}
                    {series.category ? (
                      <div className="text-xs text-muted-foreground">{series.category}</div>
                    ) : null}
                  </td>
                  <td className="py-2 text-muted-foreground">{CADENCE_LABEL[series.cadence] ?? series.cadence}</td>
                  <td className="py-2 text-right tabular-nums">{formatCurrency(series.average_amount)}</td>
                  <td className="py-2 text-right font-semibold tabular-nums">{formatCurrency(series.monthly_estimate)}</td>
                  <td className="py-2 text-muted-foreground">{formatDate(series.next_expected_date)}</td>
                  <td className="py-2 text-right">
                    <StatusBadge status={series.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Mobile cards */}
        <div className="-mx-4 -mb-4 divide-y divide-border md:hidden">
          {items.map((series) => (
            <div key={series.merchant_key} className="px-4 py-3">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate font-medium">{series.merchant_label}</div>
                  <div className="text-xs text-muted-foreground">
                    {CADENCE_LABEL[series.cadence] ?? series.cadence} · next {formatDate(series.next_expected_date)}
                  </div>
                </div>
                <div className="shrink-0 text-right">
                  <div className="font-semibold tabular-nums">{formatCurrency(series.monthly_estimate)}</div>
                  <div className="text-[11px] text-muted-foreground">/mo</div>
                </div>
              </div>
              <div className="mt-1 flex items-center gap-2">
                <StatusBadge status={series.status} />
                {!series.amount_consistent ? (
                  <span className="rounded bg-secondary px-1 py-0.5 text-[10px] text-muted-foreground">variable amount</span>
                ) : null}
              </div>
            </div>
          ))}
        </div>

        {recurring.data && items.length === 0 ? (
          <div className="grid h-24 place-items-center text-sm text-muted-foreground">
            No recurring payments detected for this filter.
          </div>
        ) : null}
        {!recurring.data ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-10 animate-pulse rounded bg-secondary" />
            ))}
          </div>
        ) : null}
      </Section>
    </AppShell>
  );
}

function StatusBadge({ status }: { status: "active" | "inactive" }) {
  return (
    <span
      className={
        "rounded px-1.5 py-0.5 text-[11px] font-medium " +
        (status === "active" ? "bg-emerald-50 text-emerald-700" : "bg-secondary text-muted-foreground")
      }
    >
      {status === "active" ? "Active" : "Inactive"}
    </span>
  );
}
