import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Check, Pencil, X } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Section } from "@/components/finance/Section";
import { KpiCard } from "@/components/finance/KpiCard";
import { getAccountsSummary, patchAccountNickname } from "@/lib/api/client";
import type { Account } from "@/lib/api/types";
import { formatCurrency } from "@/lib/format";

export default function AccountsPage() {
  const q = useQuery({ queryKey: ["accounts"], queryFn: getAccountsSummary });
  const [editingId, setEditingId] = useState<number | null>(null);
  const [draftName, setDraftName] = useState("");
  const [savingId, setSavingId] = useState<number | null>(null);
  const data = q.data;

  const startEdit = (account: Account) => {
    setEditingId(account.id);
    setDraftName(account.display_name ?? account.nickname ?? account.name);
  };

  const saveName = async (account: Account) => {
    setSavingId(account.id);
    try {
      const trimmed = draftName.trim();
      await patchAccountNickname(account.id, {
        nickname: trimmed && trimmed !== account.name ? trimmed : null,
      });
      setEditingId(null);
      await q.refetch();
    } finally {
      setSavingId(null);
    }
  };

  return (
    <AppShell>
      <div className="mb-4">
        <h1 className="text-xl font-semibold tracking-tight">Accounts</h1>
        <p className="text-sm text-muted-foreground">Balances across every linked account.</p>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        {data ? (
          <>
            <KpiCard label="Net worth" value={formatCurrency(data.net_worth, { compact: true })} tone="net" />
            <KpiCard label="Assets" value={formatCurrency(data.assets, { compact: true })} tone="income" />
            <KpiCard label="Liabilities" value={formatCurrency(data.liabilities, { compact: true })} tone="spend" />
          </>
        ) : (
          Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-[86px] animate-pulse rounded-lg bg-secondary" />
          ))
        )}
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        {data
          ? Object.entries(data.groups).map(([group, accounts]) => {
              const total = accounts.reduce((sum, a) => sum + a.current_balance, 0);
              return (
                <Section
                  key={group}
                  title={group}
                  action={
                    <span
                      className={
                        "text-sm font-semibold tabular-nums " +
                        (total < 0 ? "text-red-600" : "")
                      }
                    >
                      {formatCurrency(total, { sign: total < 0, compact: true })}
                    </span>
                  }
                >
                  <ul className="-mx-4 -mb-4 divide-y divide-border">
                    {accounts.map((a) => (
                      <li key={a.id} className="flex items-center gap-3 px-4 py-3">
                        <div className="min-w-0 flex-1">
                          {editingId === a.id ? (
                            <div className="flex items-center gap-1.5">
                              <input
                                value={draftName}
                                onChange={(e) => setDraftName(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") saveName(a);
                                  if (e.key === "Escape") setEditingId(null);
                                }}
                                autoFocus
                                className="h-8 min-w-0 flex-1 rounded-md border border-input bg-background px-2 text-sm"
                              />
                              <button
                                type="button"
                                onClick={() => saveName(a)}
                                disabled={savingId === a.id}
                                aria-label="Save account display name"
                                className="grid h-8 w-8 shrink-0 place-items-center rounded-md border border-input text-emerald-700 hover:bg-secondary disabled:opacity-50"
                              >
                                <Check className="h-4 w-4" />
                              </button>
                              <button
                                type="button"
                                onClick={() => setEditingId(null)}
                                aria-label="Cancel account display name edit"
                                className="grid h-8 w-8 shrink-0 place-items-center rounded-md border border-input text-muted-foreground hover:bg-secondary"
                              >
                                <X className="h-4 w-4" />
                              </button>
                            </div>
                          ) : (
                            <div className="flex items-center gap-2">
                              <div className="truncate text-sm font-medium">{a.display_name ?? a.name}</div>
                              <button
                                type="button"
                                onClick={() => startEdit(a)}
                                aria-label="Edit account display name"
                                className="grid h-7 w-7 shrink-0 place-items-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground"
                              >
                                <Pencil className="h-3.5 w-3.5" />
                              </button>
                            </div>
                          )}
                          <div className="text-xs text-muted-foreground">
                            {a.subtype ?? "account"}
                            {a.mask ? ` · ••${a.mask}` : ""}
                            {a.nickname ? ` · ${a.name}` : ""}
                            {a.credit_limit
                              ? ` · limit ${formatCurrency(a.credit_limit, { compact: true })}`
                              : ""}
                          </div>
                        </div>
                        <div
                          className={
                            "shrink-0 text-right text-sm font-semibold tabular-nums " +
                            (a.current_balance < 0 ? "text-red-600" : "")
                          }
                        >
                          {formatCurrency(Math.abs(a.current_balance))}
                        </div>
                      </li>
                    ))}
                  </ul>
                </Section>
              );
            })
          : Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-48 animate-pulse rounded-lg bg-secondary" />
            ))}
      </div>
    </AppShell>
  );
}
