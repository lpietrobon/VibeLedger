import { CartesianGrid, Line, LineChart, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { TimelineSpike } from "@/lib/api/client";
import { formatCurrency } from "@/lib/format";

export function SpendingTimelineChart({ days, spikes, onSelect }: {
  days: { date: string; amount: number }[];
  spikes: TimelineSpike[];
  onSelect: (date: string) => void;
}) {
  const noteworthy = spikes.slice().sort((a, b) => b.excess - a.excess).slice(0, 12);
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={days} onClick={(point) => {
        if (point?.activeLabel) onSelect(String(point.activeLabel));
      }} margin={{ left: -8, right: 8, top: 12, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(0 0% 90%)" vertical={false} />
        <XAxis dataKey="date" tick={{ fontSize: 10 }} tickLine={false} axisLine={false} minTickGap={30}
          tickFormatter={(v: string) => v.slice(5)} />
        <YAxis tick={{ fontSize: 10 }} tickFormatter={(v: number) => `$${Math.round(v / 1000)}k`} width={42} />
        <Tooltip formatter={(v: number) => formatCurrency(v)} labelFormatter={(v) => `Posted spending · ${v}`} />
        <Line type="linear" dataKey="amount" name="Daily spend" stroke="#ef4444" strokeWidth={2} dot={false} isAnimationActive={false} />
        {noteworthy.map((s) => <ReferenceDot key={s.date} x={s.date} y={s.observed} r={5}
          fill="#b91c1c" stroke="#fff" strokeWidth={1} />)}
      </LineChart>
    </ResponsiveContainer>
  );
}
