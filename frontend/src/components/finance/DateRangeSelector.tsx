import type { ComparisonRule, DatePreset, DateRangeSelection } from "@/lib/dateRange";
import { COMPARISON_RULES, RANGE_PRESETS, comparisonBounds, localToday, presetBounds, validateRange } from "@/lib/dateRange";

export function DateRangeSelector({ value, onChange, allowAll = false }: {
  value: DateRangeSelection;
  onChange: (next: DateRangeSelection) => void;
  allowAll?: boolean;
}) {
  const selectPreset = (preset: DatePreset) => {
    const dates = preset === "custom"
      ? { startDate: value.startDate || localToday(), endDate: value.endDate || localToday() }
      : presetBounds(preset);
    onChange({ ...value, preset, ...dates, comparison: preset === "all" ? "none" : value.comparison });
  };
  const valid = validateRange(value, allowAll && value.preset === "all");
  const previous = comparisonBounds(value, value.comparison);
  return (
    <div className="flex flex-wrap items-end gap-2 text-xs" aria-label="Reporting date range">
      <label className="flex flex-col gap-1">
        <span className="text-muted-foreground">Period</span>
        <select aria-label="Period preset" className="h-9 rounded border border-input bg-background px-2" value={value.preset}
          onChange={(e) => selectPreset(e.target.value as DatePreset)}>
          {allowAll ? <option value="all">All time</option> : null}
          {RANGE_PRESETS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
        </select>
      </label>
      <label className="flex flex-col gap-1">
        <span className="text-muted-foreground">From</span>
        <input aria-label="From date" type="date" className="h-9 rounded border border-input bg-background px-2"
          value={value.startDate} onChange={(e) => onChange({ ...value, preset: "custom", startDate: e.target.value })} />
      </label>
      <label className="flex flex-col gap-1">
        <span className="text-muted-foreground">To</span>
        <input aria-label="To date" type="date" className="h-9 rounded border border-input bg-background px-2"
          value={value.endDate} onChange={(e) => onChange({ ...value, preset: "custom", endDate: e.target.value })} />
      </label>
      <label className="flex flex-col gap-1">
        <span className="text-muted-foreground">Compare</span>
        <select aria-label="Comparison rule" className="h-9 rounded border border-input bg-background px-2"
          value={value.comparison} onChange={(e) => onChange({ ...value, comparison: e.target.value as ComparisonRule })}>
          {COMPARISON_RULES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
        </select>
      </label>
      <div className="basis-full text-muted-foreground" aria-live="polite">
        {!valid ? <span role="alert">Choose a valid From and To (From must not exceed To).</span>
          : value.preset === "all" ? "Entire recorded history"
          : `${value.startDate} – ${value.endDate}`}
        {previous ? ` · compared with ${previous.startDate} – ${previous.endDate}` : ""}
      </div>
    </div>
  );
}
