import { CartesianGrid, Line, LineChart, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { CumulativeSpendingPoint } from "@/lib/api/types";
import type { TimelineSpike } from "@/lib/api/client";
import { formatCurrency } from "@/lib/format";

const priorLines = [
  { key: "previous1", label: "1 prior", color: "#6b7280" },
  { key: "previous2", label: "2 prior", color: "#9ca3af" },
  { key: "previous3", label: "3 prior", color: "#d1d5db" },
] as const;

/** One primary cumulative view. Dates are explicit, not inferred from graph position. */
export default function CumulativeChart({ data, days = [], spikes = [], selectedDate, priorCount = 1, onSelect } : {
  data: CumulativeSpendingPoint[];
  days?: { date: string; amount: number }[];
  spikes?: TimelineSpike[];
  selectedDate?: string | null;
  priorCount?: number;
  onSelect?: (day: string) => void;
}) {
  const daily = new Map(days.map((p) => [p.date, p.amount]));
  const spikeDates = new Set(spikes.map((s) => s.date));
  const pointByDay = new Map(data.map((p) => [p.day, p]));
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data}
        onClick={(event) => {
          const point = pointByDay.get(Number(event?.activeLabel));
          if (point?.date) onSelect?.(point.date);
        }}
        margin={{ left: -12, right: 8, top: 12, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="currentColor" strokeOpacity={0.08} vertical={false} />
        <XAxis dataKey="day" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} minTickGap={26} />
        <YAxis tick={{ fontSize: 10 }} axisLine={false} tickLine={false}
          tickFormatter={(v: number) => "$" + Math.round(v / 1000) + "k"} width={44} />
        <Tooltip content={({active, payload}) => {
          if (!active || !payload?.length) return null;
          const point = payload[0]?.payload as CumulativeSpendingPoint | undefined;
          if (!point?.date) return null;
          return <div className="rounded-md border border-border bg-card p-2 text-xs shadow-md">
            <div className="font-semibold">{point.date}</div>
            <div>Cumulative: {formatCurrency(point.current ?? 0)}</div>
            <div>That day: {formatCurrency(daily.get(point.date) ?? 0)}</div>
            <div className="mt-1 text-muted-foreground">Tap to inspect</div>
          </div>;
        }} />
        {priorLines.slice(0, priorCount).map((line) =>
          <Line key={line.key} type="linear" dataKey={line.key} name={line.label}
            stroke={line.color} strokeWidth={1.8} strokeDasharray="5 3"
            dot={false} isAnimationActive={false} connectNulls={false} />
        )}
        <Line type="linear" dataKey="current" name="Current" stroke="#2563eb"
          strokeWidth={2.8} dot={false} activeDot={{ r: 5 }}
          isAnimationActive={false} connectNulls={false} />
        {data.filter((p) => p.date && spikeDates.has(p.date) && p.current !== null).map((p) =>
          <ReferenceDot key={p.date} x={p.day} y={p.current!} r={4}
            fill="#f59e0b" stroke="#fff" strokeWidth={1.5}
            onClick={() => onSelect?.(p.date!)} />
        )}
        {data.filter((p) => p.date === selectedDate && p.current !== null).map((p) =>
          <ReferenceDot key={"selected-" + p.date} x={p.day} y={p.current!} r={6}
            fill="#2563eb" stroke="#fff" strokeWidth={2} />
        )}
      </LineChart>
    </ResponsiveContainer>
  );
}
