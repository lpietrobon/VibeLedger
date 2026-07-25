import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { CumulativeSpendingPoint } from "@/lib/api/types";
import { formatCurrency } from "@/lib/format";

export default function CumulativeChart({ data }: { data: CumulativeSpendingPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={{ left: -10, right: 8, top: 8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(0 0% 90%)" vertical={false} />
        <XAxis dataKey="day" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis
          tick={{ fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
          width={40}
        />
        <Tooltip
          formatter={(v: number) => (v == null ? "—" : formatCurrency(v))}
          contentStyle={{ fontSize: 12, borderRadius: 6 }}
        />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <Line type="linear" dataKey="previous3" name="3 ago" stroke="#cbd5e1" strokeWidth={1} dot={false} />
        <Line type="linear" dataKey="previous2" name="2 ago" stroke="#94a3b8" strokeWidth={1} dot={false} />
        <Line type="linear" dataKey="previous1" name="Prior" stroke="#64748b" strokeWidth={1.5} dot={false} />
        <Line type="linear" dataKey="current" name="Current" stroke="#ef4444" strokeWidth={2.5} dot={false} connectNulls={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
