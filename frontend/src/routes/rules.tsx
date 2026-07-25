import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Plus, Play, X, Trash2, Pencil } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Section } from "@/components/finance/Section";
import {
  CATEGORIES,
  applyCategoryRules,
  createCategoryRule,
  deleteCategoryRule,
  getCategoryRules,
  patchCategoryRule,
} from "@/lib/api/client";
import type { CategoryRule, CategoryRuleDraft } from "@/lib/api/types";
import { formatCurrency } from "@/lib/format";

export default function RulesPage() {
  const queryClient = useQueryClient();
  const rules = useQuery({ queryKey: ["category-rules"], queryFn: getCategoryRules });
  const [editing, setEditing] = useState<CategoryRule | "new" | null>(null);
  const [applyMsg, setApplyMsg] = useState<string | null>(null);

  const items = rules.data?.items ?? [];
  const active = items.filter((rule) => rule.enabled).length;
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["category-rules"] });

  const toggle = useMutation({
    mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) => patchCategoryRule(id, { enabled }),
    onSuccess: invalidate,
  });

  const apply = useMutation({
    mutationFn: applyCategoryRules,
    onSuccess: (data) => {
      setApplyMsg(`Applied — ${data.updated_count} annotations updated, ${data.would_change_count} categories changed.`);
      invalidate();
    },
    onError: (e) => setApplyMsg((e as Error).message),
  });

  return (
    <AppShell>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Category Rules</h1>
          <p className="text-sm text-muted-foreground">
            {rules.data ? `${active} active · ${items.length} total` : "Loading..."}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => apply.mutate()}
            disabled={apply.isPending}
            className="inline-flex h-9 items-center gap-1.5 rounded-md border border-input px-3 text-sm font-medium hover:bg-secondary disabled:opacity-60"
          >
            <Play className="h-3.5 w-3.5" />
            {apply.isPending ? "Applying…" : "Apply rules"}
          </button>
          <button
            onClick={() => setEditing("new")}
            className="inline-flex h-9 items-center gap-1.5 rounded-md bg-foreground px-3 text-sm font-medium text-background hover:bg-foreground/90"
          >
            <Plus className="h-3.5 w-3.5" />
            New rule
          </button>
        </div>
      </div>

      {applyMsg ? (
        <div className="mb-3 rounded-md border border-border bg-secondary/40 px-3 py-2 text-sm text-muted-foreground">
          {applyMsg}
        </div>
      ) : null}

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
                <th className="py-2 text-right font-medium">Enabled</th>
                <th className="py-2 text-right font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {items.map((rule) => (
                <tr key={rule.id} className="border-b border-border hover:bg-secondary/40">
                  <td className="py-2 text-muted-foreground">{rule.rank}</td>
                  <td className="py-2 font-medium">{rule.name || `Rule ${rule.id}`}</td>
                  <td className="max-w-[360px] py-2">
                    <div className="truncate">{rule.description_regex || "Any description"}</div>
                    {rule.account_name_regex ? (
                      <div className="truncate text-xs text-muted-foreground">{rule.account_name_regex}</div>
                    ) : null}
                  </td>
                  <td className="py-2 text-muted-foreground">{formatAmountRange(rule.min_amount, rule.max_amount)}</td>
                  <td className="py-2">{rule.assigned_category}</td>
                  <td className="py-2 text-right">
                    <input
                      type="checkbox"
                      checked={rule.enabled}
                      onChange={() => toggle.mutate({ id: rule.id, enabled: !rule.enabled })}
                      aria-label={`Toggle ${rule.name || rule.id}`}
                      className="h-4 w-4"
                    />
                  </td>
                  <td className="py-2 text-right">
                    <button
                      onClick={() => setEditing(rule)}
                      className="grid h-7 w-7 place-items-center rounded hover:bg-secondary"
                      aria-label="Edit rule"
                    >
                      <Pencil className="h-3.5 w-3.5 text-muted-foreground" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="-mx-4 -mb-4 divide-y divide-border md:hidden">
          {items.map((rule) => (
            <button
              key={rule.id}
              onClick={() => setEditing(rule)}
              className="block w-full px-4 py-3 text-left text-sm hover:bg-secondary/40"
            >
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0 font-medium">{rule.name || `Rule ${rule.id}`}</div>
                <span
                  className={
                    "shrink-0 rounded px-1.5 py-0.5 text-[11px] font-medium " +
                    (rule.enabled ? "bg-emerald-50 text-emerald-700" : "bg-secondary text-muted-foreground")
                  }
                >
                  {rule.enabled ? "On" : "Off"}
                </span>
              </div>
              <div className="mt-1 truncate text-xs text-muted-foreground">
                {rule.description_regex || "Any description"}
              </div>
              <div className="mt-2 flex items-center justify-between gap-3">
                <span>{rule.assigned_category}</span>
                <span className="text-xs text-muted-foreground">{formatAmountRange(rule.min_amount, rule.max_amount)}</span>
              </div>
            </button>
          ))}
        </div>

        {rules.data && items.length === 0 ? (
          <div className="grid h-24 place-items-center text-sm text-muted-foreground">
            No category rules yet — create one to auto-categorize transactions.
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

      {editing ? (
        <RuleSheet
          rule={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            invalidate();
            setEditing(null);
          }}
        />
      ) : null}
    </AppShell>
  );
}

function RuleSheet({
  rule,
  onClose,
  onSaved,
}: {
  rule: CategoryRule | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState<CategoryRuleDraft>({
    name: rule?.name ?? "",
    rank: rule?.rank ?? 100,
    enabled: rule?.enabled ?? true,
    description_regex: rule?.description_regex ?? "",
    account_name_regex: rule?.account_name_regex ?? "",
    min_amount: rule?.min_amount ?? null,
    max_amount: rule?.max_amount ?? null,
    assigned_category: rule?.assigned_category ?? "",
  });
  const [error, setError] = useState<string | null>(null);

  useEffect(() => setError(null), [form]);

  const save = useMutation({
    mutationFn: () => {
      const payload: CategoryRuleDraft = {
        ...form,
        name: form.name || null,
        description_regex: form.description_regex || null,
        account_name_regex: form.account_name_regex || null,
        min_amount: numOrNull(form.min_amount),
        max_amount: numOrNull(form.max_amount),
      };
      return rule ? patchCategoryRule(rule.id, payload) : createCategoryRule(payload);
    },
    onSuccess: onSaved,
    onError: (e) => setError((e as Error).message),
  });

  const remove = useMutation({
    mutationFn: () => deleteCategoryRule(rule!.id),
    onSuccess: onSaved,
    onError: (e) => setError((e as Error).message),
  });

  const canSave = Boolean(form.assigned_category) && Boolean(
    form.description_regex || form.account_name_regex || form.min_amount != null || form.max_amount != null,
  );

  return (
    <>
      <div className="fixed inset-0 z-40 bg-foreground/20 backdrop-blur-[1px]" onClick={onClose} aria-hidden />
      <aside
        className="fixed inset-x-0 bottom-0 z-50 max-h-[92vh] overflow-y-auto rounded-t-lg border-t border-border bg-background shadow-xl md:inset-y-0 md:right-0 md:left-auto md:max-h-none md:w-[420px] md:rounded-none md:border-l md:border-t-0"
        role="dialog"
        aria-label="Edit rule"
      >
        <div className="sticky top-0 flex items-center justify-between border-b border-border bg-background px-4 py-3">
          <div className="text-sm font-semibold">{rule ? "Edit rule" : "New rule"}</div>
          <button onClick={onClose} className="grid h-8 w-8 place-items-center rounded-md hover:bg-secondary" aria-label="Close">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-3 px-4 py-4">
          <RuleField label="Name">
            <input
              value={form.name ?? ""}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="e.g. Coffee shops"
              className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
            />
          </RuleField>
          <RuleField label="Description matches (regex)">
            <input
              value={form.description_regex ?? ""}
              onChange={(e) => setForm((f) => ({ ...f, description_regex: e.target.value }))}
              placeholder="starbucks|blue bottle"
              className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm font-mono"
            />
          </RuleField>
          <RuleField label="Account matches (regex)">
            <input
              value={form.account_name_regex ?? ""}
              onChange={(e) => setForm((f) => ({ ...f, account_name_regex: e.target.value }))}
              placeholder="optional"
              className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm font-mono"
            />
          </RuleField>
          <div className="grid grid-cols-2 gap-3">
            <RuleField label="Min amount">
              <input
                type="number"
                step="0.01"
                value={form.min_amount ?? ""}
                onChange={(e) => setForm((f) => ({ ...f, min_amount: e.target.value === "" ? null : Number(e.target.value) }))}
                className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
              />
            </RuleField>
            <RuleField label="Max amount">
              <input
                type="number"
                step="0.01"
                value={form.max_amount ?? ""}
                onChange={(e) => setForm((f) => ({ ...f, max_amount: e.target.value === "" ? null : Number(e.target.value) }))}
                className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
              />
            </RuleField>
          </div>
          <RuleField label="Assign category">
            <input
              value={form.assigned_category}
              onChange={(e) => setForm((f) => ({ ...f, assigned_category: e.target.value.toUpperCase() }))}
              list="rule-category-options"
              placeholder="FOOD/COFFEE"
              className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
            />
            <datalist id="rule-category-options">
              {CATEGORIES.map((c) => (
                <option key={c} value={c} />
              ))}
            </datalist>
          </RuleField>
          <div className="grid grid-cols-2 gap-3">
            <RuleField label="Rank (lower wins)">
              <input
                type="number"
                value={form.rank ?? 100}
                onChange={(e) => setForm((f) => ({ ...f, rank: Number(e.target.value) }))}
                className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
              />
            </RuleField>
            <label className="mt-6 flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.enabled ?? true}
                onChange={(e) => setForm((f) => ({ ...f, enabled: e.target.checked }))}
                className="h-4 w-4"
              />
              Enabled
            </label>
          </div>

          {error ? <p className="text-sm text-red-600">{error}</p> : null}

          <div className="flex gap-2 pt-2">
            {rule ? (
              <button
                onClick={() => remove.mutate()}
                disabled={remove.isPending}
                className="inline-flex h-10 items-center gap-1.5 rounded-md border border-red-200 px-3 text-sm font-medium text-red-600 hover:bg-red-50 disabled:opacity-60"
              >
                <Trash2 className="h-4 w-4" />
                Delete
              </button>
            ) : null}
            <button
              onClick={() => save.mutate()}
              disabled={!canSave || save.isPending}
              className="ml-auto flex-1 rounded-md bg-foreground px-3 py-2 text-sm font-medium text-background hover:bg-foreground/90 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {save.isPending ? "Saving…" : "Save rule"}
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}

function RuleField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</label>
      {children}
    </div>
  );
}

function numOrNull(v: number | null | undefined) {
  return v == null || Number.isNaN(v) ? null : v;
}

function formatAmountRange(min?: number | null, max?: number | null) {
  if (min == null && max == null) return "Any";
  if (min != null && max != null) return `${formatCurrency(min)}-${formatCurrency(max)}`;
  if (min != null) return `>= ${formatCurrency(min)}`;
  return `<= ${formatCurrency(max ?? 0)}`;
}
