import type { ReactNode } from "react";

export function KpiCard({
  label,
  value,
  sublabel,
  delta,
  tone = "neutral",
}: {
  label: string;
  value: ReactNode;
  sublabel?: ReactNode;
  delta?: ReactNode;
  tone?: "neutral" | "income" | "spend" | "net" | "attention";
}) {
  const accent =
    tone === "income"
      ? "before:bg-emerald-500"
      : tone === "spend"
        ? "before:bg-red-500"
        : tone === "net"
          ? "before:bg-sky-500"
          : tone === "attention"
            ? "before:bg-amber-500"
            : "before:bg-transparent";
  return (
    <div
      className={
        "relative overflow-hidden rounded-lg border border-border bg-card p-3 pl-4 before:absolute before:left-0 before:top-0 before:h-full before:w-1 " +
        accent
      }
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          {label}
        </span>
        {delta}
      </div>
      <div className="mt-1 truncate text-xl font-semibold tabular-nums sm:text-2xl">{value}</div>
      {sublabel ? (
        <div className="mt-0.5 overflow-hidden text-[11px] leading-tight text-muted-foreground sm:text-xs">
          {sublabel}
        </div>
      ) : null}
    </div>
  );
}
