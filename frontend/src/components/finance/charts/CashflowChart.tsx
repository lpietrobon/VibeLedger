import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { CashflowPoint } from "@/lib/api/types";
import { formatCurrency, formatMonth } from "@/lib/format";

export default function CashflowChart({ data }: { data: CashflowPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <ComposedChart data={data} margin={{ left: -10, right: 8, top: 8, bottom: 0 }}>
        <defs>
          <linearGradient id="netFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#0ea5e9" stopOpacity={0.25} />
            <stop offset="100%" stopColor="#0ea5e9" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="incomeFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#10b981" stopOpacity={0.22} />
            <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="spendFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#ef4444" stopOpacity={0.18} />
            <stop offset="100%" stopColor="#ef4444" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(0 0% 90%)" vertical={false} />
        <XAxis dataKey="month" tickFormatter={formatMonth} tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis
          tick={{ fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
          width={40}
        />
        <Tooltip
          formatter={(v: number) => formatCurrency(v)}
          labelFormatter={(l: string) => formatMonth(l) + " " + l.slice(0, 4)}
          contentStyle={{ fontSize: 12, borderRadius: 6 }}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Area type="monotone" dataKey="income" name="Income" stroke="#10b981" strokeOpacity={0.4} fill="url(#incomeFill)" strokeWidth={1} />
        <Area type="monotone" dataKey="expenses" name="Spending" stroke="#ef4444" strokeOpacity={0.4} fill="url(#spendFill)" strokeWidth={1} />
        <Line type="monotone" dataKey="net" name="Net" stroke="#0ea5e9" strokeWidth={2.5} dot={{ r: 2 }} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
