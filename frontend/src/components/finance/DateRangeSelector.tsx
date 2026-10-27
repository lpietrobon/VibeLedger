import { useState } from "react";
import type { DatePreset, DateRangeSelection } from "@/lib/dateRange";
import { RANGE_PRESETS, localToday, presetBounds, presetComparison, validateRange } from "@/lib/dateRange";

function addMonths(day: string, months: number): string {
  const [y, m] = day.split("-").map(Number);
  const d = new Date(Date.UTC(y, m - 1 + months, 1));
  return d.toISOString().slice(0, 7);
}
function monthGrid(month: string): Array<string | null> {
  const [y, m] = month.split("-").map(Number);
  const first = new Date(Date.UTC(y, m - 1, 1));
  const offset = first.getUTCDay();
  const days = new Date(Date.UTC(y, m, 0)).getUTCDate();
  return [...Array<null>(offset).fill(null),
    ...Array.from({ length: days }, (_, i) => month + "-" + String(i + 1).padStart(2, "0"))];
}

export function DateRangeSelector({ value, onChange, allowAll = false }: {
  value: DateRangeSelection;
  onChange: (next: DateRangeSelection) => void;
  allowAll?: boolean;
  /** Comparison selection is derived from the preset, not displayed as another dropdown. */
  allowComparison?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [month, setMonth] = useState(() => (value.endDate || localToday()).slice(0, 7));
  const [from, setFrom] = useState<string | null>(null);
  const [to, setTo] = useState<string | null>(null);

  const selectPreset = (preset: DatePreset) => {
    if (preset === "custom") {
      setMonth((value.endDate || localToday()).slice(0, 7));
      setFrom(null);
      setTo(null);
      setOpen(true);
      return;
    }
    onChange({ ...value, preset, ...presetBounds(preset), comparison: presetComparison(preset) });
  };
  const pick = (day: string) => {
    if (!from || to) { setFrom(day); setTo(null); return; }
    if (day < from) { setTo(from); setFrom(day); } else { setTo(day); }
  };
  const apply = () => {
    if (!from || !to) return;
    const next: DateRangeSelection = {
      preset: "custom", startDate: from, endDate: to,
      comparison: "previous-period",
    };
    if (!validateRange(next)) return;
    onChange(next);
    setOpen(false);
  };
  const [year, monthNumber] = month.split("-").map(Number);
  const monthTitle = new Date(Date.UTC(year, monthNumber - 1, 1))
    .toLocaleDateString("en-US", { month: "long", year: "numeric", timeZone: "UTC" });
  return (
    <>
      <div className="flex w-full gap-1 rounded-lg bg-secondary/70 p-1" role="group" aria-label="Reporting date range">
        {RANGE_PRESETS.map(({value: preset, label}) => (
          <button type="button" key={preset} aria-label={label + " period"} aria-pressed={value.preset === preset}
            onClick={() => selectPreset(preset)}
            className={"min-w-0 flex-1 rounded-md px-1 py-2 text-xs font-medium transition-colors sm:px-3 sm:text-sm " +
              (value.preset === preset ? "bg-primary text-primary-foreground" : "hover:bg-background/60")}>
            {label}
          </button>
        ))}
        {allowAll ? <button type="button" aria-label="All time period" aria-pressed={value.preset === "all"}
          onClick={() => selectPreset("all")}
          className={"rounded-md px-2 py-2 text-xs " +
            (value.preset === "all" ? "bg-primary text-primary-foreground" : "hover:bg-background/60")}>
          All
        </button> : null}
      </div>
      {open ? (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/35 p-0 sm:items-center sm:p-4"
          onMouseDown={(event) => { if (event.target === event.currentTarget) setOpen(false); }}>
          <div role="dialog" aria-modal="true" aria-label="Select custom date range"
            className="w-full max-w-md rounded-t-2xl bg-background p-4 shadow-xl sm:rounded-xl">
            <div className="mb-4 flex items-center justify-between gap-2">
              <button type="button" onClick={() => setOpen(false)} className="px-2 py-2 text-sm text-primary">Cancel</button>
              <span className="font-semibold">Select date range</span>
              <button type="button" onClick={apply} disabled={!from || !to}
                className="rounded-md bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-40">
                Apply
              </button>
            </div>
            <p className="mb-3 text-center text-xs text-muted-foreground" aria-live="polite">
              {!from ? "Select the start date" : !to ? "Now select the end date" : from + " – " + to}
            </p>
            <div className="mb-3 flex items-center justify-between">
              <button type="button" aria-label="Previous month" onClick={() => setMonth(addMonths(month, -1))}
                className="rounded px-3 py-2 text-lg">‹</button>
              <strong>{monthTitle}</strong>
              <button type="button" aria-label="Next month" onClick={() => setMonth(addMonths(month, 1))}
                className="rounded px-3 py-2 text-lg">›</button>
            </div>
            <div className="grid grid-cols-7 gap-1 text-center text-xs">
              {["Su","Mo","Tu","We","Th","Fr","Sa"].map((d, i) =>
                <span key={i} className="py-2 text-muted-foreground">{d}</span>)}
              {monthGrid(month).map((day, i) => (
                day ? <button type="button" key={day} aria-label={day} aria-pressed={day === from || day === to}
                  onClick={() => pick(day)}
                  className={"min-h-10 rounded-md text-sm " +
                    (day === from || day === to ? "bg-primary text-primary-foreground"
                      : from && to && day > from && day < to ? "bg-primary/15" : "hover:bg-secondary")}>
                  {Number(day.slice(-2))}
                </button> : <span key={"empty-" + i} />
              ))}
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
