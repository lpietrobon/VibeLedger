import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { ArrowDownUp, CalendarDays, Edit3, X } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Section } from "@/components/finance/Section";
import { SearchBar, SearchChips } from "@/components/finance/SearchBar";
import { TransactionRow } from "@/components/finance/TransactionRow";
import { AnnotationSheet, BatchAnnotationSheet } from "@/components/finance/AnnotationSheet";
import {
  CATEGORIES,
  CATEGORY_GROUPS,
  getTransactions,
  patchTransactionAnnotation,
  patchTransactionAnnotations,
} from "@/lib/api/client";
import type { Transaction } from "@/lib/api/types";
import { formatCurrency, formatDate } from "@/lib/format";

const basePath = import.meta.env.BASE_URL.replace(/\/+$/, "");

type AttentionFilter = "unreviewed" | "uncategorized" | "refunds";
const FILTER_LABEL: Record<AttentionFilter, string> = {
  unreviewed: "Unreviewed",
  uncategorized: "Uncategorized",
  refunds: "Likely refunds",
};

/** Overview's counts are whole-ledger, so these have to filter server-side too —
 *  narrowing a single page client-side hides matches beyond it. */
const FILTER_QUERY: Record<AttentionFilter, string> = {
  unreviewed: "is:unreviewed is:not-transfer",
  uncategorized: "is:uncategorized",
  refunds: "is:likely-refund",
};

const SOURCE_LABEL: Record<string, string> = {
  manual: "Manual",
  rule: "Rule",
  plaid: "Plaid",
  default: "Auto",
};

type DatePreset = "all" | "this-month" | "last-month" | "last-30" | "this-year" | "custom";

const DATE_PRESETS: Array<{ value: DatePreset; label: string }> = [
  { value: "all", label: "All time" },
  { value: "this-month", label: "This month" },
  { value: "last-month", label: "Last month" },
  { value: "last-30", label: "Last 30 days" },
  { value: "this-year", label: "This year" },
  { value: "custom", label: "Custom" },
];

function toDateInput(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function presetBounds(preset: DatePreset) {
  const today = new Date();
  const startOfThisMonth = new Date(today.getFullYear(), today.getMonth(), 1);
  const endOfThisMonth = new Date(today.getFullYear(), today.getMonth() + 1, 0);
  const startOfLastMonth = new Date(today.getFullYear(), today.getMonth() - 1, 1);
  const endOfLastMonth = new Date(today.getFullYear(), today.getMonth(), 0);
  const last30 = new Date(today);
  last30.setDate(today.getDate() - 29);

  if (preset === "this-month") return { startDate: toDateInput(startOfThisMonth), endDate: toDateInput(endOfThisMonth) };
  if (preset === "last-month") return { startDate: toDateInput(startOfLastMonth), endDate: toDateInput(endOfLastMonth) };
  if (preset === "last-30") return { startDate: toDateInput(last30), endDate: toDateInput(today) };
  if (preset === "this-year") return { startDate: `${today.getFullYear()}-01-01`, endDate: toDateInput(today) };
  return { startDate: "", endDate: "" };
}

export default function TransactionsPage() {
  const urlParams = new URLSearchParams(window.location.search);
  const rawFilter = urlParams.get("filter");
  const filter = isAttentionFilter(rawFilter) ? rawFilter : undefined;
  const [query, setQuery] = useState(urlParams.get("query") ?? "");
  const [category, setCategory] = useState(urlParams.get("category") ?? "All");
  const [startDate, setStartDate] = useState(urlParams.get("startDate") ?? "");
  const [endDate, setEndDate] = useState(urlParams.get("endDate") ?? "");
  const [datePreset, setDatePreset] = useState<DatePreset>(startDate || endDate ? "custom" : "all");
  const [sort, setSort] = useState(urlParams.get("sort") ?? "date");
  const [order, setOrder] = useState(urlParams.get("order") ?? "desc");
  const [selected, setSelected] = useState<Transaction | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(() => new Set());
  const [batchOpen, setBatchOpen] = useState(false);
  const [onlyUnreviewed, setOnlyUnreviewed] = useState(false);
  const limit = filter || startDate || endDate || category !== "All" || query ? 500 : 100;
  const serverQuery = [filter ? FILTER_QUERY[filter] : "", query].filter(Boolean).join(" ");

  const tx = useQuery({
    queryKey: ["all-tx", serverQuery, category, startDate, endDate, limit],
    queryFn: () => getTransactions({ query: serverQuery, category, startDate, endDate, limit }),
  });

  const items = useMemo(() => {
    const filtered = (tx.data?.items ?? []).filter((t) => {
      if (onlyUnreviewed && t.annotation.reviewed) return false;
      return true;
    });

    return [...filtered].sort((a, b) => {
      const direction = order === "asc" ? 1 : -1;
      if (sort === "amount") {
        return (Math.abs(a.amount) - Math.abs(b.amount)) * direction;
      }
      const dateDiff = a.date.localeCompare(b.date);
      if (dateDiff !== 0) return dateDiff * direction;
      return (a.id - b.id) * direction;
    });
  }, [onlyUnreviewed, order, sort, tx.data?.items]);

  const clearFilter = () => {
    window.history.replaceState(null, "", `${basePath}/transactions`);
    window.location.reload();
  };

  const selectDatePreset = (nextPreset: DatePreset) => {
    setDatePreset(nextPreset);
    if (nextPreset === "custom") return;
    const bounds = presetBounds(nextPreset);
    setStartDate(bounds.startDate);
    setEndDate(bounds.endDate);
  };

  const handleSave = async (
    id: number,
    payload: Parameters<typeof patchTransactionAnnotation>[1],
  ) => {
    await patchTransactionAnnotation(id, payload);
    tx.refetch();
  };

  const selectedCount = selectedIds.size;
  const allVisibleSelected = items.length > 0 && items.every((t) => selectedIds.has(t.id));

  const toggleSelected = (id: number) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAllVisible = () => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (allVisibleSelected) {
        for (const item of items) next.delete(item.id);
      } else {
        for (const item of items) next.add(item.id);
      }
      return next;
    });
  };

  const handleBatchSave = async (
    payload: Parameters<typeof patchTransactionAnnotations>[1],
  ) => {
    const ids = Array.from(selectedIds);
    if (!ids.length) return;
    await patchTransactionAnnotations(ids, payload);
    setSelectedIds(new Set());
    tx.refetch();
  };

  return (
    <AppShell>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Transactions</h1>
          <p className="text-sm text-muted-foreground">
            {tx.data ? `${items.length} shown · ${tx.data.total} total` : "Loading…"}
          </p>
        </div>
      </div>

      <Section title="All activity">
        {filter ? (
          <div className="mb-3 inline-flex items-center gap-2 rounded-md border border-amber-300 bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-800">
            <span>Filtered from Overview: {FILTER_LABEL[filter]}</span>
            <button
              onClick={clearFilter}
              aria-label="Clear filter"
              className="grid h-4 w-4 place-items-center rounded hover:bg-amber-100"
            >
              <X className="h-3 w-3" />
            </button>
          </div>
        ) : null}
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <SearchBar value={query} onChange={setQuery} placeholder="Search or filter transactions…" />
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="h-10 min-w-0 flex-1 rounded-md border border-input bg-background px-2 text-sm md:h-9 md:flex-none"
          >
            <option value="All">All categories</option>
            {category !== "All" && !CATEGORIES.includes(category) ? (
              <option value={category}>{category}</option>
            ) : null}
            {CATEGORY_GROUPS.map((group) => (
              <optgroup key={group.label} label={group.label}>
                {group.options.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
          <div className="inline-flex h-10 min-w-0 flex-1 items-center rounded-md border border-input bg-background text-sm md:h-9 md:flex-none">
            <CalendarDays className="ml-2 h-4 w-4 text-muted-foreground" />
            <select
              value={datePreset}
              onChange={(e) => selectDatePreset(e.target.value as DatePreset)}
              aria-label="Date range"
              className="h-full bg-transparent px-2 text-sm outline-none"
            >
              {DATE_PRESETS.map((preset) => (
                <option key={preset.value} value={preset.value}>
                  {preset.label}
                </option>
              ))}
            </select>
          </div>
          {datePreset === "custom" ? (
            <>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                aria-label="Start date"
                className="h-10 min-w-0 flex-1 rounded-md border border-input bg-background px-2 text-sm md:h-9 md:flex-none"
              />
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                aria-label="End date"
                className="h-10 min-w-0 flex-1 rounded-md border border-input bg-background px-2 text-sm md:h-9 md:flex-none"
              />
            </>
          ) : null}
          <div className="inline-flex h-10 min-w-0 flex-1 items-center rounded-md border border-input bg-background text-sm md:h-9 md:flex-none">
            <ArrowDownUp className="ml-2 h-4 w-4 text-muted-foreground" />
            <select
              value={`${sort}:${order}`}
              onChange={(e) => {
                const [nextSort, nextOrder] = e.target.value.split(":");
                setSort(nextSort);
                setOrder(nextOrder);
              }}
              aria-label="Sort transactions"
              className="h-full bg-transparent px-2 text-sm outline-none"
            >
              <option value="date:desc">Newest</option>
              <option value="date:asc">Oldest</option>
              <option value="amount:desc">Highest price</option>
              <option value="amount:asc">Lowest price</option>
            </select>
          </div>
          <button
            onClick={() => setOnlyUnreviewed((v) => !v)}
            className={
              "h-10 shrink-0 rounded-md border px-3 text-xs font-medium transition-colors md:h-9 " +
              (onlyUnreviewed
                ? "border-amber-300 bg-amber-50 text-amber-800"
                : "border-input text-muted-foreground hover:bg-secondary")
            }
          >
            Needs review
          </button>
        </div>

        <SearchChips query={query} onChange={setQuery} />

        {items.length ? (
          <div className="mb-3 flex flex-wrap items-center gap-2 rounded-md border border-border bg-secondary/30 px-2 py-2 text-sm">
            <label className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
              <input
                type="checkbox"
                checked={allVisibleSelected}
                onChange={toggleAllVisible}
                className="h-4 w-4"
              />
              Select all shown
            </label>
            <span className="text-xs text-muted-foreground">{selectedCount} selected</span>
            <button
              type="button"
              onClick={() => setBatchOpen(true)}
              disabled={!selectedCount}
              className="ml-auto inline-flex h-8 items-center gap-1.5 rounded-md bg-foreground px-2.5 text-xs font-medium text-background hover:bg-foreground/90 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Edit3 className="h-3.5 w-3.5" />
              Edit selected
            </button>
            <button
              type="button"
              onClick={() => setSelectedIds(new Set())}
              disabled={!selectedCount}
              className="h-8 rounded-md border border-input px-2.5 text-xs font-medium text-muted-foreground hover:bg-background disabled:cursor-not-allowed disabled:opacity-40"
            >
              Clear
            </button>
          </div>
        ) : null}

        {/* Mobile: rows. Desktop: table. */}
        <div className="md:hidden -mx-4 -mb-4">
          {items.map((t) => (
            <div key={t.id} className="flex items-stretch border-b border-border">
              <label className="grid w-11 shrink-0 place-items-center">
                <input
                  type="checkbox"
                  checked={selectedIds.has(t.id)}
                  onChange={() => toggleSelected(t.id)}
                  aria-label={`Select ${t.effective_merchant ?? t.name}`}
                  className="h-4 w-4"
                />
              </label>
              <div className="min-w-0 flex-1">
                <TransactionRow tx={t} onClick={() => setSelected(t)} selected={selected?.id === t.id} />
              </div>
            </div>
          ))}
          {tx.data && items.length === 0 ? (
            <div className="grid h-24 place-items-center text-sm text-muted-foreground">
              No transactions match those filters.
            </div>
          ) : null}
        </div>

        <div className="hidden md:block">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-[11px] uppercase tracking-wide text-muted-foreground">
                <th className="w-8 py-2 font-medium">
                  <input
                    type="checkbox"
                    checked={allVisibleSelected}
                    onChange={toggleAllVisible}
                    aria-label="Select all shown"
                    className="h-4 w-4"
                  />
                </th>
                <th className="py-2 font-medium">Date</th>
                <th className="py-2 font-medium">Merchant</th>
                <th className="py-2 font-medium">Category</th>
                <th className="py-2 font-medium">Account</th>
                <th className="py-2 font-medium">Source</th>
                <th className="py-2 text-right font-medium">Amount</th>
                <th className="py-2 text-right font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {items.map((t) => {
                const isIncome = t.amount < 0;
                return (
                  <tr
                    key={t.id}
                    onClick={() => setSelected(t)}
                    className={
                      "cursor-pointer border-b border-border hover:bg-secondary/60 " +
                      (selected?.id === t.id ? "bg-secondary" : "")
                    }
                  >
                    <td className="py-2">
                      <input
                        type="checkbox"
                        checked={selectedIds.has(t.id)}
                        onClick={(e) => e.stopPropagation()}
                        onChange={() => toggleSelected(t.id)}
                        aria-label={`Select ${t.effective_merchant ?? t.name}`}
                        className="h-4 w-4"
                      />
                    </td>
                    <td className="py-2 text-muted-foreground">{formatDate(t.date)}</td>
                    <td className="py-2 font-medium">{t.effective_merchant ?? t.name}</td>
                    <td className="py-2">{t.effective_category}</td>
                    <td className="py-2 text-muted-foreground">{t.effective_account_name}</td>
                    <td className="py-2">
                      <span className="rounded bg-secondary px-1.5 py-0.5 text-[11px] text-muted-foreground">
                        {SOURCE_LABEL[t.category_source]}
                      </span>
                    </td>
                    <td
                      className={
                        "py-2 text-right font-semibold tabular-nums " +
                        (isIncome ? "text-emerald-700" : "")
                      }
                    >
                      {isIncome ? "+" : ""}
                      {formatCurrency(Math.abs(t.amount))}
                    </td>
                    <td className="py-2 text-right">
                      {t.is_transfer ? (
                        <span
                          className="rounded bg-sky-50 px-1.5 py-0.5 text-[11px] font-medium text-sky-700"
                          title="Part of a transfer pair — excluded from spend and income totals"
                        >
                          Transfer
                        </span>
                      ) : t.pending ? (
                        <span className="rounded bg-amber-50 px-1.5 py-0.5 text-[11px] font-medium text-amber-700">
                          Pending
                        </span>
                      ) : !t.annotation.reviewed ? (
                        <span className="rounded bg-amber-50 px-1.5 py-0.5 text-[11px] font-medium text-amber-700">
                          Review
                        </span>
                      ) : (
                        <span className="text-[11px] text-muted-foreground">Reviewed</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {tx.data && items.length === 0 ? (
            <div className="grid h-24 place-items-center text-sm text-muted-foreground">
              No transactions match those filters.
            </div>
          ) : null}
          {!tx.data ? (
            <div className="space-y-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="h-9 animate-pulse rounded bg-secondary" />
              ))}
            </div>
          ) : null}
        </div>
      </Section>

      <AnnotationSheet tx={selected} onClose={() => setSelected(null)} onSave={handleSave} />
      <BatchAnnotationSheet
        count={batchOpen ? selectedCount : 0}
        onClose={() => setBatchOpen(false)}
        onSave={handleBatchSave}
      />
    </AppShell>
  );
}

function isAttentionFilter(value: string | null): value is AttentionFilter {
  return value === "unreviewed" || value === "uncategorized" || value === "refunds";
}
