/** Canonical date-only reporting ranges. No monetary calculations run in the browser. */
export type DatePreset = "current-month" | "current-year" | "last-30" | "last-365" | "custom" | "all";
export type ComparisonRule = "none" | "previous-month" | "previous-year" | "previous-period";
export type DateRange = { startDate: string; endDate: string };
export type DateRangeSelection = DateRange & { preset: DatePreset; comparison: ComparisonRule };

export const RANGE_PRESETS: ReadonlyArray<{ value: DatePreset; label: string }> = [
  { value: "last-30", label: "30D" },
  { value: "last-365", label: "1Y" },
  { value: "current-month", label: "Month" },
  { value: "current-year", label: "Year" },
  { value: "custom", label: "Custom" },
];

export const COMPARISON_RULES: ReadonlyArray<{ value: ComparisonRule; label: string }> = [
  { value: "none", label: "No comparison" },
  { value: "previous-month", label: "Previous month" },
  { value: "previous-year", label: "Previous year" },
  { value: "previous-period", label: "Preceding equal period" },
];

export function localToday(now: Date = new Date()): string {
  return [now.getFullYear(), String(now.getMonth() + 1).padStart(2, "0"), String(now.getDate()).padStart(2, "0")].join("-");
}

function parseDay(value: string): Date {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) throw new Error("Invalid ISO calendar date");
  const [year, month, day] = value.split("-").map(Number);
  const result = new Date(Date.UTC(year, month - 1, day));
  if (result.getUTCFullYear() !== year || result.getUTCMonth() !== month - 1 || result.getUTCDate() !== day) {
    throw new Error("Invalid calendar day");
  }
  return result;
}

function fmtDay(day: Date): string { return day.toISOString().slice(0, 10); }
function offsetDays(value: string, days: number): string {
  const d = parseDay(value);
  d.setUTCDate(d.getUTCDate() + days);
  return fmtDay(d);
}
function shiftCalendar(value: string, offset: number, unit: "month" | "year"): string {
  const d = parseDay(value);
  const year = d.getUTCFullYear() + (unit === "year" ? offset : 0);
  const month0 = d.getUTCMonth() + (unit === "month" ? offset : 0);
  const first = new Date(Date.UTC(year, month0, 1));
  const last = new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth() + 1, 0)).getUTCDate();
  first.setUTCDate(Math.min(d.getUTCDate(), last));
  return fmtDay(first);
}

export function validateRange(range: DateRange, allowAll = false): boolean {
  if (allowAll && !range.startDate && !range.endDate) return true;
  try { parseDay(range.startDate); parseDay(range.endDate); } catch { return false; }
  return range.startDate <= range.endDate;
}

export function presetBounds(preset: DatePreset, today: string = localToday()): DateRange {
  const t = parseDay(today);
  if (preset === "current-month") return { startDate: today.slice(0, 7) + "-01", endDate: today };
  if (preset === "current-year") return { startDate: today.slice(0, 4) + "-01-01", endDate: today };
  if (preset === "last-30") return { startDate: offsetDays(today, -29), endDate: today };
  if (preset === "last-365") return { startDate: offsetDays(today, -364), endDate: today };
  if (preset === "all") return { startDate: "", endDate: "" };
  return { startDate: fmtDay(t), endDate: fmtDay(t) };
}

export function initialDateSelection(preset: DatePreset = "current-month", today: string = localToday()): DateRangeSelection {
  return { preset, comparison: "none", ...presetBounds(preset, today) };
}

export function comparisonBounds(range: DateRange, rule: ComparisonRule): DateRange | null {
  if (rule === "none" || !validateRange(range)) return null;
  if (rule === "previous-month") return {
    startDate: shiftCalendar(range.startDate, -1, "month"),
    endDate: shiftCalendar(range.endDate, -1, "month"),
  };
  if (rule === "previous-year") return {
    startDate: shiftCalendar(range.startDate, -1, "year"),
    endDate: shiftCalendar(range.endDate, -1, "year"),
  };
  const days = Math.round((parseDay(range.endDate).getTime() - parseDay(range.startDate).getTime()) / 86400000) + 1;
  return { startDate: offsetDays(range.startDate, -days), endDate: offsetDays(range.startDate, -1) };
}

export function rangeQuery(selection: DateRangeSelection) {
  if (!validateRange(selection, selection.preset === "all")) return null;
  const prior = defaultComparison(selection);
  return { startDate: selection.startDate || undefined, endDate: selection.endDate || undefined,
    compareStartDate: prior?.startDate, compareEndDate: prior?.endDate };
}

/** One source of truth for the exact comparison dates used by every chart. */
export function comparisonPeriods(selection: DateRangeSelection, count: number): DateRange[] {
  if (!validateRange(selection) || !Number.isInteger(count) || count < 0 || count > 3) {
    if (count === 0) return [];
    throw new Error("Invalid comparison period request");
  }
  const periods: DateRange[] = [];
  for (let i = 1; i <= count; i++) {
    if (selection.preset === "current-month") {
      periods.push({
        startDate: shiftCalendar(selection.startDate, -i, "month"),
        endDate: shiftCalendar(selection.endDate, -i, "month"),
      });
    } else if (selection.preset === "current-year") {
      periods.push({
        startDate: shiftCalendar(selection.startDate, -i, "year"),
        endDate: shiftCalendar(selection.endDate, -i, "year"),
      });
    } else {
      const length = Math.round((parseDay(selection.endDate).getTime() - parseDay(selection.startDate).getTime()) / 86400000) + 1;
      periods.push({
        startDate: offsetDays(selection.startDate, -i * length),
        endDate: offsetDays(selection.endDate, -i * length),
      });
    }
  }
  return periods;
}

/** KPI comparison always uses one prior window, even if no historical lines are drawn. */
export function defaultComparison(selection: DateRangeSelection): DateRange | null {
  return selection.preset === "all" ? null : comparisonPeriods(selection, 1)[0];
}

export function presetComparison(preset: DatePreset): ComparisonRule {
  if (preset === "current-month") return "previous-month";
  if (preset === "current-year") return "previous-year";
  return preset === "all" ? "none" : "previous-period";
}

/** Centralized chart resolution. A selected month plots daily rather than a single month bucket. */
export function trendGranularity(range: DateRange): "daily" | "monthly" {
  if (!validateRange(range)) return "monthly";
  const days = Math.round((parseDay(range.endDate).getTime() - parseDay(range.startDate).getTime()) / 86400000) + 1;
  return days <= 45 ? "daily" : "monthly";
}
