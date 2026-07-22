import type { Transaction } from "@/lib/api/types";
import { formatCurrency, formatDate } from "@/lib/format";
import { CATEGORIES } from "@/lib/api/client";
import { X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

type AnnotationPayload = {
  user_category?: string | null;
  merchant_name_override?: string | null;
  notes?: string | null;
  reviewed?: boolean;
  refund_status?: "confirmed" | "not_refund" | "auto" | null;
};

export function AnnotationSheet({
  tx,
  onClose,
  onSave,
}: {
  tx: Transaction | null;
  onClose: () => void;
  onSave: (id: number, payload: AnnotationPayload) => void;
}) {
  const [category, setCategory] = useState("");
  const [merchant, setMerchant] = useState("");
  const [notes, setNotes] = useState("");
  const [reviewed, setReviewed] = useState(false);
  const [refund, setRefund] = useState<"auto" | "confirmed" | "not_refund">("auto");

  useEffect(() => {
    if (!tx) return;
    setCategory(tx.annotation.user_category ?? tx.effective_category);
    setMerchant(tx.annotation.merchant_name_override ?? tx.effective_merchant ?? "");
    setNotes(tx.annotation.notes ?? "");
    setReviewed(tx.annotation.reviewed);
    setRefund(
      tx.refund_status === "confirmed"
        ? "confirmed"
        : tx.refund_status === "not_refund"
          ? "not_refund"
          : "auto",
    );
  }, [tx]);

  const categoryOptions = useMemo(() => {
    const normalized = normalizeCategory(category);
    if (!normalized || CATEGORIES.includes(normalized)) return CATEGORIES;
    return [normalized, ...CATEGORIES];
  }, [category]);

  if (!tx) return null;

  const bankCategory = tx.plaid_category_friendly ?? tx.plaid_category_primary ?? "Uncategorized";
  const bankCategoryDetail =
    tx.plaid_category_detailed && tx.plaid_category_detailed !== tx.plaid_category_primary
      ? tx.plaid_category_detailed
      : null;
  const sourceLabel = categorySourceLabel(tx.category_source);
  const selectedCategory = normalizeCategory(category) || tx.effective_category;
  const categoryListId = `category-options-${tx.id}`;

  const handleSave = () => {
    const isInheritedSelection =
      tx.category_source !== "manual" && selectedCategory === tx.effective_category;

    onSave(tx.id, {
      user_category: isInheritedSelection ? null : selectedCategory,
      merchant_name_override: merchant || null,
      notes: notes || null,
      reviewed,
      refund_status: refund,
    });
    onClose();
  };

  return (
    <>
      <div
        className="fixed inset-0 z-40 bg-foreground/20 backdrop-blur-[1px]"
        onClick={onClose}
        aria-hidden
      />
      <aside
        className="fixed inset-x-0 bottom-0 z-50 max-h-[92vh] overflow-y-auto rounded-t-lg border-t border-border bg-background shadow-xl md:inset-y-0 md:right-0 md:left-auto md:max-h-none md:w-[400px] md:rounded-none md:border-l md:border-t-0"
        role="dialog"
        aria-label="Edit transaction"
      >
        <div className="sticky top-0 flex items-center justify-between border-b border-border bg-background px-4 py-3">
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold">
              {tx.effective_merchant ?? tx.name}
            </div>
            <div className="text-xs text-muted-foreground">
              {formatDate(tx.date)} · {tx.effective_account_name}
            </div>
          </div>
          <button
            onClick={onClose}
            className="grid h-8 w-8 place-items-center rounded-md text-muted-foreground hover:bg-secondary"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="px-4 py-4">
          <div className="mb-4 flex items-baseline justify-between">
            <span className="text-xs uppercase tracking-wide text-muted-foreground">Amount</span>
            <span
              className={
                "text-2xl font-semibold tabular-nums " +
                (tx.amount < 0 ? "text-emerald-700" : "text-foreground")
              }
            >
              {tx.amount < 0 ? "+" : ""}
              {formatCurrency(Math.abs(tx.amount))}
            </span>
          </div>

          <div className="mb-4 rounded-md border border-border bg-secondary/40 px-3 py-2">
            <div className="mb-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
              Original (from bank)
            </div>
            <dl className="space-y-1 text-xs">
              <div className="flex gap-2">
                <dt className="w-24 shrink-0 text-muted-foreground">Description</dt>
                <dd className="min-w-0 flex-1 break-words font-medium text-foreground">{tx.name}</dd>
              </div>
              <div className="flex gap-2">
                <dt className="w-24 shrink-0 text-muted-foreground">Merchant</dt>
                <dd className="min-w-0 flex-1 break-words text-foreground">
                  {tx.merchant_name ?? "—"}
                </dd>
              </div>
              <div className="flex gap-2">
                <dt className="w-24 shrink-0 text-muted-foreground">Category</dt>
                <dd className="min-w-0 flex-1 break-words text-foreground">
                  {bankCategory}
                  {bankCategoryDetail ? (
                    <span className="ml-1 text-muted-foreground">({bankCategoryDetail})</span>
                  ) : null}
                </dd>
              </div>
            </dl>
          </div>

          <div className="mb-3 rounded-md border border-border px-3 py-2">
            <div className="mb-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
              Current mapping
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="break-words text-sm font-semibold">{tx.effective_category}</span>
              <span className="rounded bg-secondary px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground">
                {sourceLabel}
              </span>
            </div>
            {tx.category_source === "manual" ? (
              <div className="mt-1 text-xs text-muted-foreground">
                Saved manual override.
              </div>
            ) : (
              <div className="mt-1 text-xs text-muted-foreground">
                Saving this category unchanged keeps the automatic mapping.
              </div>
            )}
          </div>

          <Field label="Category">
            <input
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              onBlur={(e) => setCategory(normalizeCategory(e.target.value))}
              list={categoryListId}
              placeholder="FOOD/DINING"
              className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
            />
            <datalist id={categoryListId}>
              {categoryOptions.map((c) => (
                <option key={c} value={c} />
              ))}
            </datalist>
            <div className="mt-1 flex items-center justify-between gap-2 text-xs text-muted-foreground">
              <span>After save</span>
              <span className="min-w-0 truncate font-medium text-foreground">{selectedCategory}</span>
            </div>
          </Field>

          <Field label="Merchant override">
            <input
              value={merchant}
              onChange={(e) => setMerchant(e.target.value)}
              placeholder="e.g. Blue Bottle Coffee"
              className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
            />
          </Field>

          <Field label="Notes">
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              className="w-full rounded-md border border-input bg-background p-2 text-sm"
            />
          </Field>

          <Field label="Refund status">
            <div className="grid grid-cols-3 gap-1 rounded-md bg-secondary p-1">
              {(["auto", "confirmed", "not_refund"] as const).map((r) => (
                <button
                  key={r}
                  onClick={() => setRefund(r)}
                  className={
                    "rounded px-2 py-1 text-xs font-medium capitalize transition-colors " +
                    (refund === r
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground")
                  }
                >
                  {r === "not_refund" ? "Not refund" : r}
                </button>
              ))}
            </div>
          </Field>

          <label className="mt-4 flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm">
            <span>Mark as reviewed</span>
            <input
              type="checkbox"
              checked={reviewed}
              onChange={(e) => setReviewed(e.target.checked)}
              className="h-4 w-4"
            />
          </label>

          <div className="mt-4 flex gap-2">
            <button
              onClick={onClose}
              className="flex-1 rounded-md border border-input px-3 py-2 text-sm font-medium hover:bg-secondary"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              className="flex-1 rounded-md bg-foreground px-3 py-2 text-sm font-medium text-background hover:bg-foreground/90"
            >
              Save
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}

export function BatchAnnotationSheet({
  count,
  onClose,
  onSave,
}: {
  count: number;
  onClose: () => void;
  onSave: (payload: AnnotationPayload) => void;
}) {
  const [category, setCategory] = useState("");
  const [merchant, setMerchant] = useState("");
  const [notes, setNotes] = useState("");
  const [reviewed, setReviewed] = useState(false);
  const [refund, setRefund] = useState<"auto" | "confirmed" | "not_refund">("auto");
  const [dirty, setDirty] = useState<Record<string, boolean>>({});

  const categoryOptions = useMemo(() => {
    const normalized = normalizeCategory(category);
    if (!normalized || CATEGORIES.includes(normalized)) return CATEGORIES;
    return [normalized, ...CATEGORIES];
  }, [category]);

  if (!count) return null;

  const markDirty = (field: string) => setDirty((current) => ({ ...current, [field]: true }));
  const selectedCategory = normalizeCategory(category);
  const hasChanges = Object.values(dirty).some(Boolean);

  const handleSave = () => {
    const payload: AnnotationPayload = {};
    if (dirty.category) payload.user_category = selectedCategory || null;
    if (dirty.merchant) payload.merchant_name_override = merchant || null;
    if (dirty.notes) payload.notes = notes || null;
    if (dirty.reviewed) payload.reviewed = reviewed;
    if (dirty.refund) payload.refund_status = refund;
    onSave(payload);
    onClose();
  };

  return (
    <>
      <div
        className="fixed inset-0 z-40 bg-foreground/20 backdrop-blur-[1px]"
        onClick={onClose}
        aria-hidden
      />
      <aside
        className="fixed inset-x-0 bottom-0 z-50 max-h-[92vh] overflow-y-auto rounded-t-lg border-t border-border bg-background shadow-xl md:inset-y-0 md:right-0 md:left-auto md:max-h-none md:w-[400px] md:rounded-none md:border-l md:border-t-0"
        role="dialog"
        aria-label="Batch edit transactions"
      >
        <div className="sticky top-0 flex items-center justify-between border-b border-border bg-background px-4 py-3">
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold">Batch edit</div>
            <div className="text-xs text-muted-foreground">{count} selected transactions</div>
          </div>
          <button
            onClick={onClose}
            className="grid h-8 w-8 place-items-center rounded-md text-muted-foreground hover:bg-secondary"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="px-4 py-4">
          <div className="mb-3 rounded-md border border-border px-3 py-2 text-xs text-muted-foreground">
            Only fields you change here will be applied.
          </div>

          <Field label="Category">
            <input
              value={category}
              onChange={(e) => {
                setCategory(e.target.value);
                markDirty("category");
              }}
              onBlur={(e) => setCategory(normalizeCategory(e.target.value))}
              list="batch-category-options"
              placeholder="Leave unchanged"
              className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
            />
            <datalist id="batch-category-options">
              {categoryOptions.map((c) => (
                <option key={c} value={c} />
              ))}
            </datalist>
          </Field>

          <Field label="Merchant override">
            <input
              value={merchant}
              onChange={(e) => {
                setMerchant(e.target.value);
                markDirty("merchant");
              }}
              placeholder="Leave unchanged"
              className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
            />
          </Field>

          <Field label="Notes">
            <textarea
              value={notes}
              onChange={(e) => {
                setNotes(e.target.value);
                markDirty("notes");
              }}
              rows={3}
              placeholder="Leave unchanged"
              className="w-full rounded-md border border-input bg-background p-2 text-sm"
            />
          </Field>

          <Field label="Refund status">
            <div className="grid grid-cols-3 gap-1 rounded-md bg-secondary p-1">
              {(["auto", "confirmed", "not_refund"] as const).map((r) => (
                <button
                  key={r}
                  onClick={() => {
                    setRefund(r);
                    markDirty("refund");
                  }}
                  className={
                    "rounded px-2 py-1 text-xs font-medium capitalize transition-colors " +
                    (refund === r && dirty.refund
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground")
                  }
                >
                  {r === "not_refund" ? "Not refund" : r}
                </button>
              ))}
            </div>
          </Field>

          <label className="mt-4 flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm">
            <span>Mark as reviewed</span>
            <input
              type="checkbox"
              checked={reviewed}
              onChange={(e) => {
                setReviewed(e.target.checked);
                markDirty("reviewed");
              }}
              className="h-4 w-4"
            />
          </label>

          <div className="mt-4 flex gap-2">
            <button
              onClick={onClose}
              className="flex-1 rounded-md border border-input px-3 py-2 text-sm font-medium hover:bg-secondary"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={!hasChanges}
              className="flex-1 rounded-md bg-foreground px-3 py-2 text-sm font-medium text-background hover:bg-foreground/90 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Apply
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mt-3">
      <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </label>
      {children}
    </div>
  );
}

function categorySourceLabel(source: Transaction["category_source"]) {
  switch (source) {
    case "manual":
      return "Manual override";
    case "rule":
      return "Rule";
    case "plaid":
      return "Bank";
    case "default":
      return "Default";
  }
}

function normalizeCategory(value: string) {
  return value.trim().replace(/\s+/g, "_").replace(/\/+/g, "/").toUpperCase();
}
