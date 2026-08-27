"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { CHART, tooltipStyle } from "@/lib/chartTheme";
import { fmtMonth, pkr } from "@/lib/format";
import type { MonthlyPoint } from "@/lib/types";

export function CashflowChart({ series }: { series: MonthlyPoint[] }) {
  const data = series.map((m) => ({
    month: fmtMonth(m.month),
    inflow: m.inflow_pkr,
    outflow: m.outflow_pkr,
    onTime: m.utility_paid_on_time,
  }));

  return (
    <div>
      <div className="mb-2 flex items-center gap-4 text-mono-sm text-ink-muted">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-2" style={{ background: CHART.brand }} /> Inflow
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-2" style={{ background: "#c3cddb" }} /> Outflow
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-full border border-band-low" /> Utility paid on time
        </span>
      </div>
      <div className="h-[220px] w-full">
        <ResponsiveContainer>
          <AreaChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: 8 }}>
            <CartesianGrid vertical={false} stroke={CHART.rule} />
            <XAxis
              dataKey="month"
              axisLine={false}
              tickLine={false}
              tick={{ ...CHART.axisTick }}
              interval="preserveStartEnd"
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              width={44}
              tick={{ ...CHART.axisTick }}
              tickFormatter={(v) => `${Math.round(v / 1000)}k`}
            />
            <Tooltip
              cursor={{ stroke: CHART.rule }}
              contentStyle={tooltipStyle()}
              formatter={(v: number, name) => [pkr(v), name === "inflow" ? "Inflow" : "Outflow"]}
            />
            <Area
              type="monotone"
              dataKey="outflow"
              stroke="#9aa9bf"
              strokeWidth={1.5}
              fill="#c3cddb"
              fillOpacity={0.1}
              isAnimationActive={false}
            />
            <Area
              type="monotone"
              dataKey="inflow"
              stroke={CHART.brand}
              strokeWidth={1.5}
              fill={CHART.brand}
              fillOpacity={0.1}
              isAnimationActive={false}
              dot={(props) => {
                const { cx, cy, index } = props as { cx: number; cy: number; index: number };
                if (!data[index]?.onTime) return <g key={index} />;
                return <circle key={index} cx={cx} cy={cy} r={2.5} fill="none" stroke="var(--band-low)" strokeWidth={1.5} />;
              }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-1 text-caption text-ink-faint">
        Monthly wallet inflow and outflow over the last {series.length} months. Ringed points are
        months the electricity bill was paid on time.
      </p>
    </div>
  );
}
