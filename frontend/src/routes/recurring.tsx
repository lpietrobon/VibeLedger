import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ChevronRight } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Section } from "@/components/finance/Section";
import { KpiCard } from "@/components/finance/KpiCard";
import { getRecurring, setRecurringStatus } from "@/lib/api/client";
import type { RecurringSeries } from "@/lib/api/types";
import { formatCurrency, formatDate } from "@/lib/format";

type StatusFilter = "active" | "all" | "inactive";

const CADENCE_LABEL: Record<string, string> = {
  weekly: "Weekly",
  biweekly: "Every 2 weeks",
  monthly: "Monthly",
  quarterly: "Quarterly",
  yearly: "Yearly",
};

const basePath = import.meta.env.BASE_URL.replace(/\/+$/, "");

// The series' own search_query, never merchant_label: the label is one raw
// sample name and can carry a per-transaction suffix (a Zelle confirmation
// code, a store number). Search ANDs free-text tokens, so a label-derived query
// would return only the single transaction that suffix came from.
function txHref(series: RecurringSeries) {
  return `${basePath}/transactions?query=${encodeURIComponent(series.search_query)}`;
}

export default function RecurringPage() {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<StatusFilter>("active");

  const recurring = useQuery({
    queryKey: ["recurring", status],
    queryFn: () => getRecurring(status === "all" ? {} : { status }),
  });

  const setStatusMutation = useMutation({
    mutationFn: ({ key, value }: { key: string; value: "auto" | "kept" | "canceled" }) =>
      setRecurringStatus(key, value),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["recurring"] }),
  });

  const items = recurring.data?.items ?? [];
  const summary = recurring.data?.summary;
  const onSet = (key: string, value: "auto" | "kept" | "canceled") =>
    setStatusMutation.mutate({ key, value });

  return (
    <AppShell>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Recurring</h1>
          <p className="text-sm text-muted-foreground">
            Subscriptions & recurring payments, inferred from your history. Tap one to see its charges.
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
                <th className="py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {items.map((series) => (
                <tr key={series.merchant_key} className="border-b border-border hover:bg-secondary/40">
                  <td className="py-2">
                    <a href={txHref(series)} className="group inline-flex items-center gap-1 font-medium text-sky-700 hover:underline">
                      {series.merchant_label}
                      <ChevronRight className="h-3 w-3 opacity-0 transition-opacity group-hover:opacity-100" />
                    </a>
                    {!series.amount_consistent ? (
                      <span className="ml-2 rounded bg-secondary px-1 py-0.5 text-[10px] text-muted-foreground">variable</span>
                    ) : null}
                    {series.category ? <div className="text-xs text-muted-foreground">{series.category}</div> : null}
                  </td>
                  <td className="py-2 text-muted-foreground">{CADENCE_LABEL[series.cadence] ?? series.cadence}</td>
                  <td className="py-2 text-right tabular-nums">{formatCurrency(series.average_amount)}</td>
                  <td className="py-2 text-right font-semibold tabular-nums">{formatCurrency(series.monthly_estimate)}</td>
                  <td className="py-2 text-muted-foreground">{formatDate(series.next_expected_date)}</td>
                  <td className="py-2">
                    <StatusControl series={series} onSet={onSet} />
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
              <a href={txHref(series)} className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-1 truncate font-medium text-sky-700">
                    {series.merchant_label}
                    <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {CADENCE_LABEL[series.cadence] ?? series.cadence} · next {formatDate(series.next_expected_date)}
                  </div>
                </div>
                <div className="shrink-0 text-right">
                  <div className="font-semibold tabular-nums text-foreground">{formatCurrency(series.monthly_estimate)}</div>
                  <div className="text-[11px] text-muted-foreground">/mo</div>
                </div>
              </a>
              <div className="mt-2 flex items-center gap-2">
                <StatusControl series={series} onSet={onSet} />
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

function StatusControl({
  series,
  onSet,
}: {
  series: RecurringSeries;
  onSet: (key: string, value: "auto" | "kept" | "canceled") => void;
}) {
  const badge = statusBadge(series);
  const value = series.manual_status ?? "auto";
  return (
    <div className="flex items-center gap-2">
      <span
        className={"rounded px-1.5 py-0.5 text-[11px] font-medium " + badge.className}
        title={series.manual_status ? `Manually set · detector says ${series.auto_status}` : "Auto-detected"}
      >
        {badge.text}
      </span>
      <select
        value={value}
        onChange={(e) => {
          e.stopPropagation();
          onSet(series.merchant_key, e.target.value as "auto" | "kept" | "canceled");
        }}
        aria-label={`Set status for ${series.merchant_label}`}
        className="h-7 rounded-md border border-input bg-background px-1 text-xs text-muted-foreground"
      >
        <option value="auto">Auto</option>
        <option value="kept">Keep active</option>
        <option value="canceled">Canceled</option>
      </select>
    </div>
  );
}

function statusBadge(series: RecurringSeries): { text: string; className: string } {
  if (series.manual_status === "canceled") {
    return { text: "Canceled", className: "bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-200" };
  }
  if (series.manual_status === "kept") {
    return { text: "Kept active", className: "bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-200" };
  }
  if (series.status === "active") {
    return { text: "Active", className: "bg-emerald-50 text-emerald-700" };
  }
  return { text: "Inactive", className: "bg-secondary text-muted-foreground" };
}
