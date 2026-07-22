import type { CategoryComparisonPoint } from "@/lib/api/types";
import { formatCurrency } from "@/lib/format";

export function CategoryComparison({
  data,
  currentLabel = "This month",
  previousLabel = "Last month",
  getCategoryHref,
}: {
  data: CategoryComparisonPoint[];
  currentLabel?: string;
  previousLabel?: string;
  getCategoryHref?: (category: string) => string;
}) {
  const max = Math.max(1, ...data.map((d) => Math.max(d.current, d.previous)));
  const sorted = [...data].sort((a, b) => Math.max(b.current, b.previous) - Math.max(a.current, a.previous));

  return (
    <div>
      <div className="mb-3 flex items-center gap-4 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-sm bg-foreground" />
          {currentLabel}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-sm bg-muted-foreground/40" />
          {previousLabel}
        </span>
      </div>
      <ul className="space-y-3">
        {sorted.map((row) => {
          const diff = row.current - row.previous;
          const diffTone =
            Math.abs(diff) < 1
              ? "text-muted-foreground"
              : diff > 0
                ? "text-red-600"
                : "text-emerald-700";
          return (
            <li key={row.category} className="text-sm">
              <div className="mb-1 flex items-center justify-between gap-2">
                {getCategoryHref ? (
                  <a
                    href={getCategoryHref(row.category)}
                    className="truncate font-medium text-sky-700 hover:underline"
                  >
                    {row.category}
                  </a>
                ) : (
                  <span className="truncate font-medium">{row.category}</span>
                )}
                <div className="flex shrink-0 items-center gap-2 tabular-nums">
                  <span>{formatCurrency(row.current, { compact: true })}</span>
                  <span className={"text-xs " + diffTone}>
                    {diff === 0 ? "±0" : (diff > 0 ? "+" : "-") + formatCurrency(Math.abs(diff), { compact: true })}
                  </span>
                </div>
              </div>
              <div className="space-y-1">
                <div className="h-2 overflow-hidden rounded-sm bg-secondary">
                  <div
                    className="h-full rounded-sm bg-foreground"
                    style={{ width: `${(row.current / max) * 100}%` }}
                  />
                </div>
                <div className="h-2 overflow-hidden rounded-sm bg-secondary">
                  <div
                    className="h-full rounded-sm bg-muted-foreground/40"
                    style={{ width: `${(row.previous / max) * 100}%` }}
                  />
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
