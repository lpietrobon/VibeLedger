import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/AppShell";
import { Section } from "@/components/finance/Section";
import { getTransfers } from "@/lib/api/client";
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
  const transfers = useQuery({ queryKey: ["transfers"], queryFn: getTransfers });
  const items = transfers.data?.items ?? [];
  const pending = items.filter((item) => !item.confirmed).length;

  return (
    <AppShell>
      <div className="mb-4">
        <h1 className="text-xl font-semibold tracking-tight">Transfer Detection</h1>
        <p className="text-sm text-muted-foreground">
          {transfers.data ? `${pending} pending · ${items.length} candidates` : "Loading..."}
        </p>
      </div>

      <Section title="Suspect transfers">
        <div className="hidden md:block">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-[11px] uppercase tracking-wide text-muted-foreground">
                <th className="py-2 font-medium">Date</th>
                <th className="py-2 font-medium">Out</th>
                <th className="py-2 font-medium">In</th>
                <th className="py-2 text-right font-medium">Amount</th>
                <th className="py-2 text-right font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} className="border-b border-border">
                  <td className="py-2 text-muted-foreground">
                    {item.out.date ? formatDate(item.out.date) : "-"}
                  </td>
                  <td className="py-2">
                    <a className="font-medium text-sky-700 hover:underline" href={txHref(item.out.date, item.out.name)}>
                      {item.out.name ?? `Transaction ${item.out.transaction_id}`}
                    </a>
                  </td>
                  <td className="py-2">
                    <a className="font-medium text-sky-700 hover:underline" href={txHref(item.in.date, item.in.name)}>
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
                <span className="rounded bg-amber-50 px-1.5 py-0.5 text-[11px] font-medium text-amber-700">
                  {item.confirmed ? "Confirmed" : "Pending"}
                </span>
              </div>
              <a className="block truncate font-medium text-sky-700" href={txHref(item.out.date, item.out.name)}>
                {item.out.name ?? `Transaction ${item.out.transaction_id}`}
              </a>
              <a className="mt-1 block truncate font-medium text-sky-700" href={txHref(item.in.date, item.in.name)}>
                {item.in.name ?? `Transaction ${item.in.transaction_id}`}
              </a>
              <div className="mt-1 text-xs text-muted-foreground">
                {item.out.date ? formatDate(item.out.date) : "-"} · {item.detected_by}
              </div>
            </div>
          ))}
        </div>

        {transfers.data && items.length === 0 ? (
          <div className="grid h-24 place-items-center text-sm text-muted-foreground">
            No transfer candidates.
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
