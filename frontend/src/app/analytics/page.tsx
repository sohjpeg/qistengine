"use client";

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { KpiRow, KpiStat } from "@/components/KpiStat";
import { BackendBanner } from "@/components/ui/BackendBanner";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { Disclaimer } from "@/components/ui/Disclaimer";
import { Skeleton } from "@/components/ui/Skeleton";
import { CHART, tooltipStyle } from "@/lib/chartTheme";
import { BAND_HEX } from "@/lib/utils";
import { fmtDate, pct, pkr } from "@/lib/format";
import { api, ApiError } from "@/lib/api";
import type { MetricsResponse, ModelInfoResponse, RiskBand } from "@/lib/types";

export default function AnalyticsPage() {
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
  const [model, setModel] = useState<ModelInfoResponse | null>(null);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    Promise.all([api.metrics(), api.modelInfo()])
      .then(([m, mi]) => {
        setMetrics(m);
        setModel(mi);
      })
      .catch((e) => {
        if (e instanceof ApiError && e.offline) setOffline(true);
      });
  }, []);

  if (offline) {
    return (
      <div>
        <h1 className="mb-5 text-h1 text-ink">Portfolio analytics</h1>
        <BackendBanner />
        <p className="text-body text-ink-muted">
          Analytics are computed live from the scored portfolio in the database and need the
          backend running.
        </p>
      </div>
    );
  }

  if (!metrics || !model) {
    return (
      <div className="grid gap-6 sm:grid-cols-2">
        <Skeleton className="h-64 sm:col-span-2" />
        <Skeleton className="h-64" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  const bandOrder: RiskBand[] = ["LOW", "MEDIUM", "HIGH", "VERY_HIGH"];
  const approvalByBand = bandOrder.map((b) => ({
    band: b.replace("_", " "),
    rate: metrics.approval_rate_by_band[b] ?? 0,
    key: b,
  }));

  return (
    <div>
      <h1 className="mb-5 text-h1 text-ink">Portfolio analytics</h1>

      <KpiRow>
        <KpiStat label="Applications" value={String(metrics.applications_total)} />
        <KpiStat label="Approval rate" value={pct(metrics.approval_rate)} />
        <KpiStat label="Mean score" value={metrics.mean_score.toFixed(0)} />
        <KpiStat label="Expected loss" value={pkr(metrics.portfolio_expected_loss_pkr, { compact: true })} />
        <KpiStat label="Override rate" value={pct(metrics.override_rate)} />
      </KpiRow>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Score distribution</CardTitle>
          </CardHeader>
          <CardBody>
            <div className="h-[240px]">
              <ResponsiveContainer>
                <BarChart data={metrics.score_histogram}>
                  <CartesianGrid vertical={false} stroke={CHART.rule} />
                  <XAxis dataKey="range" axisLine={false} tickLine={false} tick={{ ...CHART.axisTick }} interval={0} angle={-30} textAnchor="end" height={50} />
                  <YAxis axisLine={false} tickLine={false} width={30} tick={{ ...CHART.axisTick }} />
                  <Tooltip contentStyle={tooltipStyle()} cursor={{ fill: "var(--surface-sunk)" }} />
                  <Bar dataKey="count" radius={[2, 2, 0, 0]}>
                    {metrics.score_histogram.map((h, i) => (
                      <Cell key={i} fill={BAND_HEX[h.band]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <p className="mt-1 text-caption text-ink-faint">
              Scored applications by 300–850 score bucket, coloured by risk band.
            </p>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Approval rate by band</CardTitle>
          </CardHeader>
          <CardBody>
            <div className="h-[240px]">
              <ResponsiveContainer>
                <BarChart data={approvalByBand} layout="vertical" margin={{ left: 24 }}>
                  <CartesianGrid horizontal={false} stroke={CHART.rule} />
                  <XAxis type="number" domain={[0, 1]} axisLine={false} tickLine={false} tick={{ ...CHART.axisTick }} tickFormatter={(v) => `${Math.round(v * 100)}%`} />
                  <YAxis type="category" dataKey="band" axisLine={false} tickLine={false} width={72} tick={{ ...CHART.axisTick }} />
                  <Tooltip contentStyle={tooltipStyle()} cursor={{ fill: "var(--surface-sunk)" }} formatter={(v: number) => pct(v)} />
                  <Bar dataKey="rate" radius={[0, 2, 2, 0]}>
                    {approvalByBand.map((d) => (
                      <Cell key={d.key} fill={BAND_HEX[d.key]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <p className="mt-1 text-caption text-ink-faint">Decided applications only.</p>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>City breakdown</CardTitle>
          </CardHeader>
          <CardBody className="overflow-x-auto">
            <table className="w-full min-w-[380px] text-body">
              <thead className="text-label uppercase text-ink-muted">
                <tr>
                  <th className="py-1 text-start font-medium">City</th>
                  <th className="py-1 text-end font-medium">Apps</th>
                  <th className="py-1 text-end font-medium">Mean score</th>
                  <th className="py-1 text-end font-medium">Approval</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule font-mono text-mono-sm">
                {metrics.city_breakdown.map((c) => (
                  <tr key={c.city}>
                    <td className="py-1.5 font-sans text-ink">{c.city}</td>
                    <td className="py-1.5 text-end tabular-nums text-ink">{c.applications}</td>
                    <td className="py-1.5 text-end tabular-nums text-ink">{c.mean_score.toFixed(0)}</td>
                    <td className="py-1.5 text-end tabular-nums text-ink-muted">{pct(c.approval_rate, 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Override-rate trend</CardTitle>
          </CardHeader>
          <CardBody>
            <div className="h-[240px]">
              <ResponsiveContainer>
                <LineChart data={metrics.override_trend}>
                  <CartesianGrid vertical={false} stroke={CHART.rule} />
                  <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ ...CHART.axisTick }} tickFormatter={(d) => fmtDate(d)} />
                  <YAxis axisLine={false} tickLine={false} width={36} domain={[0, 1]} tick={{ ...CHART.axisTick }} tickFormatter={(v) => `${Math.round(v * 100)}%`} />
                  <Tooltip contentStyle={tooltipStyle()} formatter={(v: number) => pct(v)} labelFormatter={(l) => fmtDate(String(l))} />
                  <Line type="monotone" dataKey="rate" stroke={CHART.brand} strokeWidth={1.5} dot={{ r: 2, fill: CHART.brand }} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <p className="mt-1 text-caption text-ink-faint">
              Share of decisions flagged as an override, by day. A governance metric.
            </p>
          </CardBody>
        </Card>
      </div>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Model card</CardTitle>
          <span className="font-mono text-mono-sm text-ink-faint">{model.version}</span>
        </CardHeader>
        <CardBody>
          <div className="grid gap-x-8 gap-y-2 sm:grid-cols-3">
            <Metric k="ROC-AUC" v={model.metrics.roc_auc?.toFixed(3)} />
            <Metric k="PR-AUC" v={model.metrics.pr_auc?.toFixed(3)} />
            <Metric k="KS statistic" v={model.metrics.ks?.toFixed(3)} />
            <Metric k="Gini" v={model.metrics.gini?.toFixed(3)} />
            <Metric k="Brier score" v={model.metrics.brier?.toFixed(3)} />
            <Metric k="Logistic baseline AUC" v={model.metrics.logistic_baseline_auc?.toFixed(3)} />
            <Metric k="Base default rate" v={pct(model.base_rate)} />
            <Metric k="Features" v={String(model.n_features)} />
            <Metric k="Trained" v={model.trained_at ? fmtDate(model.trained_at) : "—"} />
          </div>
          {model.fairness_summary ? (
            <div className="mt-4 border-t border-rule pt-3">
              <p className="text-label uppercase text-ink-muted">Fairness audit</p>
              <ul className="mt-1 space-y-0.5 text-body text-ink-muted">
                {model.fairness_summary.headlines.map((h, i) => (
                  <li key={i}>· {h}</li>
                ))}
              </ul>
              <p className="mt-1 text-caption text-ink-faint">
                Full audit in <code className="font-mono">docs/RESPONSIBLE_AI.md</code>.
              </p>
            </div>
          ) : null}
        </CardBody>
      </Card>

      <Disclaimer className="mt-6" />
    </div>
  );
}

function Metric({ k, v }: { k: string; v?: string }) {
  return (
    <div className="flex items-baseline justify-between border-b border-rule py-1">
      <span className="text-body text-ink-muted">{k}</span>
      <span className="font-mono text-figure tabular-nums text-ink">{v ?? "—"}</span>
    </div>
  );
}
