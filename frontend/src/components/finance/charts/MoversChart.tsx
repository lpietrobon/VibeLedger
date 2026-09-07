import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { CategoryMover } from "@/lib/api/types";
import { formatCurrency } from "@/lib/format";

const INCREASE_COLOR = "#ef4444";
const DECREASE_COLOR = "#10b981";
const FLAT_COLOR = "#94a3b8";

export default function MoversChart({ data }: { data: CategoryMover[] }) {
  const rows = data.slice().reverse();
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={rows} layout="vertical" margin={{ left: 0, right: 12, top: 4, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(0 0% 90%)" horizontal={false} />
        <XAxis
          type="number"
          tick={{ fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => `${v < 0 ? "-" : ""}$${(Math.abs(v) / 1000).toFixed(1)}k`}
        />
        <YAxis dataKey="category" type="category" tick={{ fontSize: 9 }} axisLine={false} tickLine={false} width={150} />
        <Tooltip
          formatter={(v: number) => formatCurrency(v, { sign: true })}
          contentStyle={{ fontSize: 12, borderRadius: 6 }}
        />
        <Bar dataKey="change" radius={[0, 4, 4, 0]}>
          {rows.map((row) => (
            <Cell
              key={row.category}
              fill={row.change > 0 ? INCREASE_COLOR : row.change < 0 ? DECREASE_COLOR : FLAT_COLOR}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
