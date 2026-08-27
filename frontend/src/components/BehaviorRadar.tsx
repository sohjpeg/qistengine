"use client";

import {
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from "recharts";
import { CHART } from "@/lib/chartTheme";
import type { BehavioralMetrics } from "@/lib/types";

const AXES: { key: keyof BehavioralMetrics; label: string }[] = [
  { key: "payment_discipline", label: "Payment discipline" },
  { key: "cashflow_stability", label: "Cashflow stability" },
  { key: "transaction_activity", label: "Transaction activity" },
  { key: "savings_behavior", label: "Savings behaviour" },
  { key: "business_maturity", label: "Business maturity" },
  { key: "network_trust", label: "Network trust" },
];

export function BehaviorRadar({
  applicant,
  portfolioMedian,
}: {
  applicant: BehavioralMetrics;
  portfolioMedian: BehavioralMetrics;
}) {
  const data = AXES.map((a) => ({
    axis: a.label,
    applicant: applicant[a.key],
    median: portfolioMedian[a.key],
  }));

  return (
    <div>
      <div className="mb-2 flex items-center gap-4 text-mono-sm text-ink-muted">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-2" style={{ background: CHART.brand }} /> This applicant
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-3 border-b border-dashed" style={{ borderColor: CHART.inkFaint }} />{" "}
          Portfolio median
        </span>
      </div>
      <div className="h-[280px] w-full">
        <ResponsiveContainer>
          <RadarChart data={data} outerRadius="72%">
            <PolarGrid stroke={CHART.rule} />
            <PolarAngleAxis
              dataKey="axis"
              tick={{ fill: CHART.inkFaint, fontSize: 11, fontFamily: "var(--font-plex-mono)" }}
            />
            <Radar
              dataKey="median"
              stroke={CHART.inkFaint}
              strokeDasharray="4 3"
              fill="none"
              isAnimationActive={false}
            />
            <Radar
              dataKey="applicant"
              stroke={CHART.brand}
              fill={CHART.brand}
              fillOpacity={0.12}
              isAnimationActive={false}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-1 text-caption text-ink-faint">
        Six behavioural axes, 0–100, against the synthetic portfolio median.
      </p>
      <table className="sr-only">
        <tbody>
          {data.map((d) => (
            <tr key={d.axis}>
              <td>{d.axis}</td>
              <td>{d.applicant}</td>
              <td>{d.median}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
