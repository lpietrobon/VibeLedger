import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Radar, Check, Unlink } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Section } from "@/components/finance/Section";
import { confirmTransfer, deleteTransfer, detectTransfers, getTransfers } from "@/lib/api/client";
import { formatCurrency, formatDate } from "@/lib/format";

const basePath = import.meta.env.BASE_URL.replace(/\/+$/, "");

function txHref(date?: string | null, name?: string | null) {
  const params = new URLSearchParams();
  if (date) {
    params.set("startDate", date);
    params.set("endDate", date);
  }
  if (name) params.set("query", name);
  return `${basePath}/transactions?${params.toString()}`;
}

export default function TransfersPage() {
  const queryClient = useQueryClient();
  const transfers = useQuery({ queryKey: ["transfers"], queryFn: getTransfers });
  const [detectMsg, setDetectMsg] = useState<string | null>(null);
  const items = transfers.data?.items ?? [];
  const pending = items.filter((item) => !item.confirmed).length;
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["transfers"] });

  const detect = useMutation({
    mutationFn: detectTransfers,
    onSuccess: (data) => {
      setDetectMsg(`Detection complete — ${data.created} new candidate${data.created === 1 ? "" : "s"}.`);
      invalidate();
    },
    onError: (e) => setDetectMsg((e as Error).message),
  });
  const confirm = useMutation({ mutationFn: confirmTransfer, onSuccess: invalidate });
  const unpair = useMutation({ mutationFn: deleteTransfer, onSuccess: invalidate });

  return (
    <AppShell>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Transfer Detection</h1>
          <p className="text-sm text-muted-foreground">
            {transfers.data ? `${pending} pending · ${items.length} candidates` : "Loading..."}
          </p>
        </div>
        <button
          onClick={() => detect.mutate()}
          disabled={detect.isPending}
          className="inline-flex h-9 items-center gap-1.5 rounded-md bg-foreground px-3 text-sm font-medium text-background hover:bg-foreground/90 disabled:opacity-60"
        >
          <Radar className="h-3.5 w-3.5" />
          {detect.isPending ? "Detecting…" : "Detect transfers"}
        </button>
      </div>

      {detectMsg ? (
        <div className="mb-3 rounded-md border border-border bg-secondary/40 px-3 py-2 text-sm text-muted-foreground">
          {detectMsg}
        </div>
      ) : null}

      <Section title="Suspect transfers">
        <div className="hidden md:block">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-[11px] uppercase tracking-wide text-muted-foreground">
                <th className="py-2 font-medium">Date</th>
                <th className="py-2 font-medium">From → To</th>
                <th className="py-2 font-medium">Descriptions</th>
                <th className="py-2 text-right font-medium">Amount</th>
                <th className="py-2 text-right font-medium">Status</th>
                <th className="py-2 text-right font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} className="border-b border-border">
                  <td className="py-2 text-muted-foreground">{item.out.date ? formatDate(item.out.date) : "-"}</td>
                  <td className="py-2">
                    <div className="font-medium">
                      {item.out.account_name ?? `Account ${item.out.account_id}`}
                      <span className="mx-1 text-muted-foreground">→</span>
                      {item.in.account_name ?? `Account ${item.in.account_id}`}
                    </div>
                    {item.gap_days ? (
                      <div className="text-xs text-muted-foreground">
                        settles after {item.gap_days} day{item.gap_days === 1 ? "" : "s"}
                      </div>
                    ) : null}
                  </td>
                  <td className="max-w-[280px] py-2 text-muted-foreground">
                    <a className="block truncate hover:underline" href={txHref(item.out.date, item.out.name)}>
                      {item.out.name ?? `Transaction ${item.out.transaction_id}`}
                    </a>
                    <a className="block truncate hover:underline" href={txHref(item.in.date, item.in.name)}>
                      {item.in.name ?? `Transaction ${item.in.transaction_id}`}
                    </a>
                  </td>
                  <td className="py-2 text-right font-semibold tabular-nums">
                    {item.amount == null ? "-" : formatCurrency(Math.abs(item.amount))}
                  </td>
                  <td className="py-2 text-right">
                    <span
                      className={
                        "rounded px-1.5 py-0.5 text-[11px] font-medium " +
                        (item.confirmed ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700")
                      }
                    >
                      {item.confirmed ? "Confirmed" : "Pending"}
                    </span>
                  </td>
                  <td className="py-2">
                    <div className="flex items-center justify-end gap-1">
                      {!item.confirmed ? (
                        <button
                          onClick={() => confirm.mutate(item.id)}
                          disabled={confirm.isPending}
                          className="inline-flex h-7 items-center gap-1 rounded border border-emerald-200 px-2 text-xs font-medium text-emerald-700 hover:bg-emerald-50 disabled:opacity-50"
                        >
                          <Check className="h-3 w-3" /> Confirm
                        </button>
                      ) : null}
                      <button
                        onClick={() => unpair.mutate(item.id)}
                        disabled={unpair.isPending}
                        className="inline-flex h-7 items-center gap-1 rounded border border-input px-2 text-xs font-medium text-muted-foreground hover:bg-secondary disabled:opacity-50"
                      >
                        <Unlink className="h-3 w-3" /> Unpair
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="-mx-4 -mb-4 divide-y divide-border md:hidden">
          {items.map((item) => (
            <div key={item.id} className="px-4 py-3 text-sm">
              <div className="mb-2 flex items-center justify-between gap-3">
                <div className="font-semibold tabular-nums">
                  {item.amount == null ? "-" : formatCurrency(Math.abs(item.amount))}
                </div>
                <span
                  className={
                    "rounded px-1.5 py-0.5 text-[11px] font-medium " +
                    (item.confirmed ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700")
                  }
                >
                  {item.confirmed ? "Confirmed" : "Pending"}
                </span>
              </div>
              <div className="truncate font-medium">
                {item.out.account_name ?? `Account ${item.out.account_id}`}
                <span className="mx-1 text-muted-foreground">→</span>
                {item.in.account_name ?? `Account ${item.in.account_id}`}
              </div>
              <a className="mt-1 block truncate text-xs text-sky-700" href={txHref(item.out.date, item.out.name)}>
                {item.out.name ?? `Transaction ${item.out.transaction_id}`}
              </a>
              <a className="block truncate text-xs text-sky-700" href={txHref(item.in.date, item.in.name)}>
                {item.in.name ?? `Transaction ${item.in.transaction_id}`}
              </a>
              <div className="mt-1 text-xs text-muted-foreground">
                {item.out.date ? formatDate(item.out.date) : "-"} · {item.detected_by}
              </div>
              <div className="mt-2 flex items-center gap-2">
                {!item.confirmed ? (
                  <button
                    onClick={() => confirm.mutate(item.id)}
                    disabled={confirm.isPending}
                    className="inline-flex h-8 flex-1 items-center justify-center gap-1 rounded border border-emerald-200 text-xs font-medium text-emerald-700 hover:bg-emerald-50 disabled:opacity-50"
                  >
                    <Check className="h-3.5 w-3.5" /> Confirm
                  </button>
                ) : null}
                <button
                  onClick={() => unpair.mutate(item.id)}
                  disabled={unpair.isPending}
                  className="inline-flex h-8 flex-1 items-center justify-center gap-1 rounded border border-input text-xs font-medium text-muted-foreground hover:bg-secondary disabled:opacity-50"
                >
                  <Unlink className="h-3.5 w-3.5" /> Unpair
                </button>
              </div>
            </div>
          ))}
        </div>

        {transfers.data && items.length === 0 ? (
          <div className="grid h-24 place-items-center text-sm text-muted-foreground">
            No transfer candidates — run detection to find matching pairs.
          </div>
        ) : null}
        {!transfers.data ? (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-10 animate-pulse rounded bg-secondary" />
            ))}
          </div>
        ) : null}
      </Section>
    </AppShell>
  );
}
