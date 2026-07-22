import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { formatPct } from "@/lib/format";

/**
 * Renders a delta pill. `goodDirection` controls color semantics:
 *  - "up": increases are good (green), e.g. income, net worth
 *  - "down": decreases are good (green), e.g. spending
 */
export function Delta({
  current,
  previous,
  goodDirection = "up",
  className = "",
}: {
  current: number;
  previous: number;
  goodDirection?: "up" | "down";
  className?: string;
}) {
  if (!previous) return <span className={"text-xs text-muted-foreground " + className}>—</span>;
  const pct = ((current - previous) / Math.abs(previous)) * 100;
  const isUp = pct > 0.05;
  const isDown = pct < -0.05;
  const isGood = (isUp && goodDirection === "up") || (isDown && goodDirection === "down");
  const isBad = (isUp && goodDirection === "down") || (isDown && goodDirection === "up");

  const tone = isGood
    ? "text-emerald-700 bg-emerald-50"
    : isBad
      ? "text-red-700 bg-red-50"
      : "text-muted-foreground bg-secondary";

  const Icon = isUp ? ArrowUpRight : isDown ? ArrowDownRight : Minus;

  return (
    <span
      className={
        "inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-xs font-medium tabular-nums " +
        tone +
        " " +
        className
      }
    >
      <Icon className="h-3 w-3" />
      {formatPct(pct)}
    </span>
  );
}