import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/AppShell";
import { Section } from "@/components/finance/Section";
import { getCategoryRules } from "@/lib/api/client";
import { formatCurrency } from "@/lib/format";

export default function RulesPage() {
  const rules = useQuery({ queryKey: ["category-rules"], queryFn: getCategoryRules });
  const items = rules.data?.items ?? [];
  const active = items.filter((rule) => rule.enabled).length;

  return (
    <AppShell>
      <div className="mb-4">
        <h1 className="text-xl font-semibold tracking-tight">Category Rules</h1>
        <p className="text-sm text-muted-foreground">
          {rules.data ? `${active} active · ${items.length} total` : "Loading..."}
        </p>
      </div>

      <Section title="Rules">
        <div className="hidden md:block">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-[11px] uppercase tracking-wide text-muted-foreground">
                <th className="py-2 font-medium">Rank</th>
                <th className="py-2 font-medium">Name</th>
                <th className="py-2 font-medium">Match</th>
                <th className="py-2 font-medium">Amount</th>
                <th className="py-2 font-medium">Category</th>
                <th className="py-2 text-right font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {items.map((rule) => (
                <tr key={rule.id} className="border-b border-border">
                  <td className="py-2 text-muted-foreground">{rule.rank}</td>
                  <td className="py-2 font-medium">{rule.name || `Rule ${rule.id}`}</td>
                  <td className="max-w-[420px] py-2">
                    <div className="truncate">{rule.description_regex || "Any description"}</div>
                    {rule.account_name_regex ? (
                      <div className="truncate text-xs text-muted-foreground">{rule.account_name_regex}</div>
                    ) : null}
                  </td>
                  <td className="py-2 text-muted-foreground">
                    {formatAmountRange(rule.min_amount, rule.max_amount)}
                  </td>
                  <td className="py-2">{rule.assigned_category}</td>
                  <td className="py-2 text-right">
                    <span
                      className={
                        "rounded px-1.5 py-0.5 text-[11px] font-medium " +
                        (rule.enabled ? "bg-emerald-50 text-emerald-700" : "bg-secondary text-muted-foreground")
                      }
                    >
                      {rule.enabled ? "Enabled" : "Disabled"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="-mx-4 -mb-4 divide-y divide-border md:hidden">
          {items.map((rule) => (
            <div key={rule.id} className="px-4 py-3 text-sm">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0 font-medium">{rule.name || `Rule ${rule.id}`}</div>
                <div className="shrink-0 text-xs text-muted-foreground">#{rule.rank}</div>
              </div>
              <div className="mt-1 truncate text-xs text-muted-foreground">
                {rule.description_regex || "Any description"}
              </div>
              <div className="mt-2 flex items-center justify-between gap-3">
                <span>{rule.assigned_category}</span>
                <span className="text-xs text-muted-foreground">
                  {formatAmountRange(rule.min_amount, rule.max_amount)}
                </span>
              </div>
            </div>
          ))}
        </div>

        {rules.data && items.length === 0 ? (
          <div className="grid h-24 place-items-center text-sm text-muted-foreground">
            No category rules yet.
          </div>
        ) : null}
        {!rules.data ? (
          <div className="space-y-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-10 animate-pulse rounded bg-secondary" />
            ))}
          </div>
        ) : null}
      </Section>
    </AppShell>
  );
}

function formatAmountRange(min?: number | null, max?: number | null) {
  if (min == null && max == null) return "Any";
  if (min != null && max != null) return `${formatCurrency(min)}-${formatCurrency(max)}`;
  if (min != null) return `>= ${formatCurrency(min)}`;
  return `<= ${formatCurrency(max ?? 0)}`;
}
