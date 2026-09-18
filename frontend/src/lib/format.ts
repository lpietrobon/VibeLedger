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

const MONTH_ABBREVIATIONS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

/**
 * Render an API calendar date without making its result depend on the browser
 * timezone.  Transaction dates are date-based business facts: for timestamp
 * input, the leading ISO date is the rendered calendar date.
 */
export function formatDate(
  value: string | null | undefined,
  options: { referenceDate?: Date } = {},
) {
  const match = value?.match(/^(\d{4})-(\d{2})-(\d{2})(?:$|T)/);
  if (!match) return "—";

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const parsed = new Date(Date.UTC(year, month - 1, day));
  if (
    month < 1 || month > 12 || day < 1 ||
    parsed.getUTCFullYear() !== year ||
    parsed.getUTCMonth() !== month - 1 ||
    parsed.getUTCDate() !== day
  ) return "—";

  const referenceYear = (options.referenceDate ?? new Date()).getUTCFullYear();
  const formatted = `${day} ${MONTH_ABBREVIATIONS[month - 1]}`;
  return year === referenceYear ? formatted : `${formatted}, ${year}`;
}

export function deltaPct(current: number, previous: number): number | null {
  if (!previous) return null;
  return ((current - previous) / previous) * 100;
}
