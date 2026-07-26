import { useMemo } from "react";
import type { DailySpendPoint } from "@/lib/api/types";
import { formatCurrency } from "@/lib/format";

const WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const CELL = 12;
const GAP = 2;
const STEP = CELL + GAP;
const LABEL_COL_WIDTH = 28;
const HEADER_HEIGHT = 16;

// Sequential, one hue (spend intensity), light -> dark. Zero-spend days use the
// neutral secondary surface rather than the ramp's own lightest step.
const INTENSITY_STEPS = ["#fee2e2", "#fca5a5", "#f87171", "#ef4444", "#b91c1c", "#7f1d1d"];

function intensityColor(amount: number, max: number) {
  if (amount <= 0) return "rgb(148 163 184 / 0.18)";
  if (max <= 0) return INTENSITY_STEPS[0];
  // Square-root, not linear: a handful of large bills (rent) would otherwise
  // saturate the scale and flatten every ordinary day to the lightest step.
  const ratio = Math.sqrt(amount / max);
  const idx = Math.min(INTENSITY_STEPS.length - 1, Math.floor(ratio * INTENSITY_STEPS.length));
  return INTENSITY_STEPS[idx];
}

function toUtcDate(iso: string) {
  return new Date(iso + "T00:00:00Z");
}

export default function CalendarHeatmap({ year, days }: { year: number; days: DailySpendPoint[] }) {
  const { cells, weekCount, monthTicks, max } = useMemo(() => {
    const firstDay = new Date(Date.UTC(year, 0, 1));
    const firstWeekday = (firstDay.getUTCDay() + 6) % 7; // Monday = 0
    const weekZero = new Date(firstDay);
    weekZero.setUTCDate(weekZero.getUTCDate() - firstWeekday);
    const weekIndex = (d: Date) => Math.round((d.getTime() - weekZero.getTime()) / (7 * 86400000));

    let max = 0;
    for (const d of days) max = Math.max(max, d.amount);

    const cells = days.map((d) => {
      const date = toUtcDate(d.date);
      return { ...d, weekday: (date.getUTCDay() + 6) % 7, week: weekIndex(date) };
    });

    const weekCount = cells.length ? Math.max(...cells.map((c) => c.week)) + 1 : 0;
    const monthTicks = Array.from({ length: 12 }, (_, m) => ({
      week: weekIndex(new Date(Date.UTC(year, m, 1))),
      label: MONTH_LABELS[m],
    }));

    return { cells, weekCount, monthTicks, max };
  }, [year, days]);

  if (!days.length) {
    return (
      <div className="grid h-40 place-items-center text-sm text-muted-foreground">No data for {year}.</div>
    );
  }

  const width = LABEL_COL_WIDTH + weekCount * STEP;
  const height = HEADER_HEIGHT + 7 * STEP;

  return (
    <div>
      <div className="overflow-x-auto">
        <svg width={width} height={height} role="img" aria-label={`Daily spend intensity for ${year}`}>
          {monthTicks.map(({ week, label }) => (
            <text key={label} x={LABEL_COL_WIDTH + week * STEP} y={10} className="fill-muted-foreground text-[9px]">
              {label}
            </text>
          ))}
          {WEEKDAY_LABELS.map((label, i) =>
            i % 2 === 0 ? (
              <text key={label} x={0} y={HEADER_HEIGHT + i * STEP + CELL / 2 + 3} className="fill-muted-foreground text-[9px]">
                {label}
              </text>
            ) : null,
          )}
          {cells.map((c) => (
            <rect
              key={c.date}
              x={LABEL_COL_WIDTH + c.week * STEP}
              y={HEADER_HEIGHT + c.weekday * STEP}
              width={CELL}
              height={CELL}
              rx={2}
              fill={intensityColor(c.amount, max)}
            >
              <title>{`${c.date}: ${formatCurrency(c.amount)}`}</title>
            </rect>
          ))}
        </svg>
      </div>
      <div className="mt-2 flex items-center gap-1.5 text-[10px] text-muted-foreground">
        <span>Less</span>
        <span className="h-2.5 w-2.5 rounded-sm" style={{ background: "rgb(148 163 184 / 0.18)" }} />
        {INTENSITY_STEPS.map((color) => (
          <span key={color} className="h-2.5 w-2.5 rounded-sm" style={{ background: color }} />
        ))}
        <span>More</span>
      </div>
    </div>
  );
}
