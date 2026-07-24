import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { CategoryComparisonPoint } from "@/lib/api/types";
import { CATEGORY_COLORS } from "@/lib/api/theme";
import { formatCurrency } from "@/lib/format";

export default function CategoryBarChart({ data }: { data: CategoryComparisonPoint[] }) {
  const rows = data.filter((c) => c.current > 0).sort((a, b) => b.current - a.current);
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={rows} layout="vertical" margin={{ left: 0, right: 12, top: 4, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(0 0% 90%)" horizontal={false} />
        <XAxis
          type="number"
          tick={{ fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => `$${(v / 1000).toFixed(1)}k`}
        />
        <YAxis dataKey="category" type="category" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} width={92} />
        <Tooltip formatter={(v: number) => formatCurrency(v)} contentStyle={{ fontSize: 12, borderRadius: 6 }} />
        <Bar dataKey="current" radius={[0, 4, 4, 0]}>
          {rows.map((c) => (
            <Cell key={c.category} fill={CATEGORY_COLORS[c.category] ?? "#64748b"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
