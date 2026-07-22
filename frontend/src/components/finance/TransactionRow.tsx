import type { Transaction } from "@/lib/api/types";
import { formatCurrency, formatDate } from "@/lib/format";
import { AlertCircle, RotateCcw, Clock } from "lucide-react";

export function TransactionRow({
  tx,
  onClick,
  selected,
}: {
  tx: Transaction;
  onClick?: () => void;
  selected?: boolean;
}) {
  const isIncome = tx.amount < 0;
  const merchant = tx.effective_merchant ?? tx.merchant_name ?? tx.name;
  const isRefund = tx.refund_status === "likely" || tx.refund_status === "confirmed";
  const unreviewed = !tx.annotation.reviewed;

  return (
    <button
      type="button"
      onClick={onClick}
      className={
        "flex w-full items-center gap-3 border-b border-border px-3 py-3 text-left transition-colors hover:bg-secondary/60 " +
        (selected ? "bg-secondary" : "")
      }
    >
      <div className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-secondary text-xs font-semibold text-muted-foreground">
        {merchant.slice(0, 2).toUpperCase()}
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <span className="truncate text-sm font-medium">{merchant}</span>
          {tx.pending ? (
            <span className="inline-flex shrink-0 items-center gap-0.5 rounded bg-amber-50 px-1 py-0.5 text-[10px] font-medium text-amber-700">
              <Clock className="h-2.5 w-2.5" />
              Pending
            </span>
          ) : null}
          {isRefund ? (
            <span className="inline-flex shrink-0 items-center gap-0.5 rounded bg-sky-50 px-1 py-0.5 text-[10px] font-medium text-sky-700">
              <RotateCcw className="h-2.5 w-2.5" />
              Refund
            </span>
          ) : null}
          {unreviewed ? (
            <span className="inline-flex shrink-0 items-center gap-0.5 rounded bg-amber-50 px-1 py-0.5 text-[10px] font-medium text-amber-700">
              <AlertCircle className="h-2.5 w-2.5" />
              Review
            </span>
          ) : null}
        </div>
        <div className="mt-0.5 flex items-center gap-1 text-xs text-muted-foreground">
          <span className="truncate">{tx.effective_category}</span>
          <span>·</span>
          <span className="truncate">{tx.effective_account_name}</span>
          <span>·</span>
          <span className="shrink-0">{formatDate(tx.date)}</span>
        </div>
      </div>

      <div
        className={
          "shrink-0 text-right text-sm font-semibold tabular-nums " +
          (isIncome ? "text-emerald-700" : "text-foreground")
        }
      >
        {isIncome ? "+" : ""}
        {formatCurrency(Math.abs(tx.amount))}
      </div>
    </button>
  );
}