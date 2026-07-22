export function formatCurrency(n: number, opts: { compact?: boolean; sign?: boolean } = {}) {
  const abs = Math.abs(n);
  const formatted = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    notation: opts.compact && abs >= 10000 ? "compact" : "standard",
    maximumFractionDigits: abs >= 1000 && opts.compact ? 1 : 2,
  }).format(abs);
  if (opts.sign) return `${n < 0 ? "-" : "+"}${formatted}`;
  return n < 0 ? `-${formatted}` : formatted;
}

export function formatPct(n: number | null | undefined, digits = 1) {
  if (n == null || Number.isNaN(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(digits)}%`;
}

export function formatMonth(iso: string) {
  const [y, m] = iso.split("-");
  const d = new Date(Number(y), Number(m) - 1, 1);
  return d.toLocaleString("en-US", { month: "short" });
}

export function formatDate(iso: string) {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function deltaPct(current: number, previous: number): number | null {
  if (!previous) return null;
  return ((current - previous) / previous) * 100;
}