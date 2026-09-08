import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { ArrowDownUp, CalendarDays, Edit3, X } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Section } from "@/components/finance/Section";
import { SearchBar, SearchChips } from "@/components/finance/SearchBar";
import { TransactionRow } from "@/components/finance/TransactionRow";
import { AnnotationSheet, BatchAnnotationSheet } from "@/components/finance/AnnotationSheet";
import { Sheet } from "@/components/layout/Sheet";
import {
  CATEGORIES,
  CATEGORY_GROUPS,
  getTransactions,
  getDuplicateCorrections,
  createDuplicateCorrection,
  reverseDuplicateCorrection,
  patchTransactionAnnotation,
  patchTransactionAnnotations,
} from "@/lib/api/client";
import type { DuplicateCorrection, Transaction } from "@/lib/api/types";
import { formatCurrency, formatDate } from "@/lib/format";
import { invalidateLedger } from "@/lib/api/cache";

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
  refund: "Matched refund",
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
  const queryClient = useQueryClient();
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
  const [duplicateDialogOpen, setDuplicateDialogOpen] = useState(false);
  const [canonicalId, setCanonicalId] = useState<number | null>(null);
  const [reverseCorrectionId, setReverseCorrectionId] = useState<number | null>(null);
  const [duplicateError, setDuplicateError] = useState<string | null>(null);
  const [duplicateFeedback, setDuplicateFeedback] = useState<string | null>(null);
  const [onlyUnreviewed, setOnlyUnreviewed] = useState(false);
  const limit = filter || startDate || endDate || category !== "All" || query ? 500 : 100;
  const serverQuery = [filter ? FILTER_QUERY[filter] : "", query].filter(Boolean).join(" ");

  const tx = useQuery({
    queryKey: ["all-tx", serverQuery, category, startDate, endDate, limit],
    queryFn: () => getTransactions({ query: serverQuery, category, startDate, endDate, limit }),
  });

  const duplicateCorrections = useQuery({
    queryKey: ["duplicate-corrections"],
    queryFn: getDuplicateCorrections,
  });

  const activeCorrections = useMemo(
    () => (duplicateCorrections.data?.items ?? []).filter((correction) => correction.status === "active"),
    [duplicateCorrections.data?.items],
  );

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
      // Keep equal-date rows in stable ledger/import order regardless of the
      // date direction. This makes selecting a same-day pair predictable.
      return a.id - b.id;
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
    await invalidateLedger(queryClient);
  };

  const selectedCount = selectedIds.size;
  const selectedTransactions = items.filter((item) => selectedIds.has(item.id));
  const duplicateSelectionIssue = duplicateSelectionValidation(selectedTransactions, activeCorrections);
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
    await invalidateLedger(queryClient);
  };

  const openDuplicateDialog = () => {
    if (selectedCount !== 2 || duplicateSelectionIssue) return;
    setCanonicalId(selectedTransactions[0]?.id ?? null);
    setDuplicateError(null);
    setDuplicateFeedback(null);
    setDuplicateDialogOpen(true);
  };

  const handleCreateDuplicateCorrection = async () => {
    if (canonicalId === null || selectedTransactions.length !== 2) return;
    const duplicate = selectedTransactions.find((transaction) => transaction.id !== canonicalId);
    if (!duplicate) return;
    setDuplicateError(null);
    try {
      await createDuplicateCorrection({
        canonicalTransactionId: canonicalId,
        duplicateTransactionId: duplicate.id,
      });
      setDuplicateDialogOpen(false);
      setSelectedIds(new Set());
      setDuplicateFeedback("Duplicate correction saved.");
      await invalidateLedger(queryClient);
    } catch (error) {
      setDuplicateError(error instanceof Error ? error.message : "Could not save duplicate correction.");
    }
  };

  const handleReverseDuplicateCorrection = async () => {
    if (reverseCorrectionId === null) return;
    setDuplicateError(null);
    try {
      await reverseDuplicateCorrection(reverseCorrectionId);
      setReverseCorrectionId(null);
      setDuplicateFeedback("Duplicate correction reversed.");
      await invalidateLedger(queryClient);
    } catch (error) {
      setDuplicateError(error instanceof Error ? error.message : "Could not reverse duplicate correction.");
    }
  };

  const selectedRelationship = selected ? duplicateRelationshipFor(selected, activeCorrections) : undefined;
  const openRelatedTransaction = (transactionId: number) => {
    const related = items.find((item) => item.id === transactionId);
    if (related) setSelected(related);
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
        {tx.isError ? (
          <p role="alert" className="mb-3 text-sm text-red-600">Could not load transactions: {tx.error.message}</p>
        ) : null}
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
              onClick={openDuplicateDialog}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  openDuplicateDialog();
                }
              }}
              disabled={selectedCount !== 2 || Boolean(duplicateSelectionIssue)}
              className="inline-flex h-8 items-center rounded-md border border-violet-300 px-2.5 text-xs font-medium text-violet-800 hover:bg-violet-50 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Mark as duplicates
            </button>
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
        {selectedCount > 0 && duplicateSelectionIssue ? (
          <p className="mb-3 text-xs text-muted-foreground">{duplicateSelectionIssue}</p>
        ) : null}
        {duplicateFeedback ? (
          <p role="status" className="mb-3 rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
            {duplicateFeedback}
          </p>
        ) : null}
        {duplicateError ? (
          <p role="alert" className="mb-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            Duplicate correction failed: {duplicateError}
          </p>
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
                <TransactionRow
                  tx={withDuplicateStatus(t, duplicateRelationshipFor(t, activeCorrections))}
                  onClick={() => setSelected(t)}
                  selected={selected?.id === t.id}
                />
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
                const duplicateRelationship = duplicateRelationshipFor(t, activeCorrections);
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
                      {duplicateRelationship?.role === "canonical" ? (
                        <span className="rounded bg-violet-50 px-1.5 py-0.5 text-[11px] font-medium text-violet-700">
                          Canonical
                        </span>
                      ) : duplicateRelationship?.role === "duplicate" ? (
                        <span className="rounded bg-orange-50 px-1.5 py-0.5 text-[11px] font-medium text-orange-700">
                          Marked duplicate
                        </span>
                      ) : t.is_transfer ? (
                        <span
                          className="rounded bg-sky-50 px-1.5 py-0.5 text-[11px] font-medium text-sky-700"
                          title="Part of a transfer pair — excluded from spend and income totals"
                        >
                          Transfer
                        </span>
                      ) : t.is_transfer_candidate ? (
                        <span
                          className="rounded bg-amber-50 px-1.5 py-0.5 text-[11px] font-medium text-amber-700"
                          title="Possible transfer — still included in income and spending until confirmed"
                        >
                          Possible transfer · counted
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

      <AnnotationSheet
        tx={selected}
        onClose={() => setSelected(null)}
        onSave={handleSave}
        duplicateRelationship={selectedRelationship}
        onReverseDuplicate={(correctionId) => setReverseCorrectionId(correctionId)}
        onOpenRelated={openRelatedTransaction}
      />
      {duplicateDialogOpen ? (
        <DuplicateCorrectionSheet
          transactions={selectedTransactions}
          canonicalId={canonicalId}
          onCanonicalChange={setCanonicalId}
          onClose={() => setDuplicateDialogOpen(false)}
          onConfirm={handleCreateDuplicateCorrection}
          error={duplicateError}
        />
      ) : null}
      {reverseCorrectionId !== null ? (
        <DuplicateReverseSheet
          onClose={() => setReverseCorrectionId(null)}
          onConfirm={handleReverseDuplicateCorrection}
          error={duplicateError}
        />
      ) : null}
      <BatchAnnotationSheet
        count={batchOpen ? selectedCount : 0}
        onClose={() => setBatchOpen(false)}
        onSave={handleBatchSave}
      />
    </AppShell>
  );
}

function duplicateSelectionValidation(
  transactions: Transaction[],
  activeCorrections: DuplicateCorrection[],
): string | null {
  if (transactions.length !== 2) return "Select exactly two transactions to mark as duplicates.";
  if (transactions.some((transaction) => transaction.pending)) {
    return "Duplicate correction is only available for posted transactions.";
  }
  if (transactions.some((transaction) => transaction.is_transfer || transaction.is_transfer_candidate)) {
    return "Resolve transfer relationships before marking transactions as duplicates.";
  }
  if (transactions.some((transaction) => transaction.refund_status === "confirmed" || transaction.refund_status === "likely")) {
    return "Resolve refund relationships before marking transactions as duplicates.";
  }
  if (transactions.some((transaction) => activeCorrections.some(
    (correction) => correction.canonical_transaction_id === transaction.id || correction.duplicate_transaction_id === transaction.id,
  ))) {
    return "Reverse the existing duplicate correction before selecting these transactions again.";
  }
  if (transactions[0].effective_account_name !== transactions[1].effective_account_name) {
    return "Duplicate correction requires two transactions from the same account.";
  }
  if (transactions[0].amount !== transactions[1].amount) {
    return "Duplicate correction requires transactions with the same signed amount.";
  }
  if (
    transactions[0].plaid_transaction_id &&
    transactions[0].plaid_transaction_id === transactions[1].plaid_transaction_id
  ) {
    return "These rows share a provider identity; resolve the import replay instead.";
  }
  return null;
}

function duplicateRelationshipFor(
  transaction: Transaction,
  activeCorrections: DuplicateCorrection[],
) {
  const correction = activeCorrections.find(
    (candidate) =>
      candidate.canonical_transaction_id === transaction.id ||
      candidate.duplicate_transaction_id === transaction.id,
  );
  if (!correction || correction.canonical_transaction_id === null || correction.duplicate_transaction_id === null) {
    return undefined;
  }
  const role = correction.canonical_transaction_id === transaction.id ? "canonical" : "duplicate";
  return {
    correctionId: correction.id,
    role: role as "canonical" | "duplicate",
    relatedTransactionId:
      role === "canonical" ? correction.duplicate_transaction_id : correction.canonical_transaction_id,
  };
}

function withDuplicateStatus(
  transaction: Transaction,
  relationship:
    | { correctionId: number; role: "canonical" | "duplicate"; relatedTransactionId: number }
    | undefined,
): Transaction {
  if (!relationship || transaction.duplicate_status) return transaction;
  return { ...transaction, duplicate_status: relationship.role };
}

function DuplicateCorrectionSheet({
  transactions,
  canonicalId,
  onCanonicalChange,
  onClose,
  onConfirm,
  error,
}: {
  transactions: Transaction[];
  canonicalId: number | null;
  onCanonicalChange: (id: number) => void;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  error: string | null;
}) {
  return (
    <Sheet label="Duplicate correction" title="Confirm duplicate correction" onClose={onClose}>
      <div className="px-4 py-4">
        <h2 className="text-sm font-semibold">Choose the canonical transaction</h2>
        <p className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          Both imported records will remain visible. Only the record marked duplicate will be excluded from spending and income totals.
        </p>
        <fieldset className="mt-4 space-y-2">
          <legend className="sr-only">Choose the canonical transaction</legend>
          {transactions.map((transaction) => (
            <label key={transaction.id} className="flex cursor-pointer items-start gap-3 rounded-md border border-border px-3 py-3 hover:bg-secondary/60">
              <input
                type="radio"
                name="canonical-transaction"
                checked={canonicalId === transaction.id}
                onChange={() => onCanonicalChange(transaction.id)}
                className="mt-0.5 h-4 w-4"
              />
              <span className="min-w-0 text-sm">
                <span className="block font-medium">{transaction.effective_merchant ?? transaction.name}</span>
                <span className="block text-xs text-muted-foreground">
                  {formatDate(transaction.date)} · {transaction.effective_account_name} · {formatCurrency(Math.abs(transaction.amount))}
                </span>
              </span>
            </label>
          ))}
        </fieldset>
        <div className="mt-4 flex gap-2">
          <button type="button" onClick={onClose} className="flex-1 rounded-md border border-input px-3 py-2 text-sm font-medium hover:bg-secondary">
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={canonicalId === null}
            className="flex-1 rounded-md bg-foreground px-3 py-2 text-sm font-medium text-background hover:bg-foreground/90 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Confirm duplicate correction
          </button>
        </div>
        {error ? <p role="alert" className="mt-2 text-sm text-red-600">Duplicate correction failed: {error}</p> : null}
      </div>
    </Sheet>
  );
}

function DuplicateReverseSheet({
  onClose,
  onConfirm,
  error,
}: {
  onClose: () => void;
  onConfirm: () => Promise<void>;
  error: string | null;
}) {
  return (
    <Sheet level={1} label="Reverse duplicate correction" title="Reverse duplicate correction" onClose={onClose}>
      <div className="px-4 py-4">
        <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          Both records will again count normally.
        </p>
        <div className="mt-4 flex gap-2">
          <button type="button" onClick={onClose} className="flex-1 rounded-md border border-input px-3 py-2 text-sm font-medium hover:bg-secondary">
            Cancel
          </button>
          <button type="button" onClick={onConfirm} className="flex-1 rounded-md bg-foreground px-3 py-2 text-sm font-medium text-background hover:bg-foreground/90">
            Reverse correction
          </button>
        </div>
        {error ? <p role="alert" className="mt-2 text-sm text-red-600">Duplicate correction failed: {error}</p> : null}
      </div>
    </Sheet>
  );
}

function isAttentionFilter(value: string | null): value is AttentionFilter {
  return value === "unreviewed" || value === "uncategorized" || value === "refunds";
}
