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

function shortDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

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
            <div className="h-[240px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={metrics.score_histogram} margin={{ top: 4, right: 8, bottom: 24, left: 0 }}>
                  <CartesianGrid vertical={false} stroke={CHART.rule} />
                  <XAxis dataKey="range" axisLine={false} tickLine={false} tick={{ ...CHART.axisTick }} interval={0} angle={-35} textAnchor="end" height={48} />
                  <YAxis axisLine={false} tickLine={false} width={30} allowDecimals={false} tick={{ ...CHART.axisTick }} />
                  <Tooltip contentStyle={tooltipStyle()} cursor={{ fill: "var(--surface-sunk)" }} />
                  <Bar dataKey="count" radius={[2, 2, 0, 0]} isAnimationActive={false}>
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
            <div className="h-[240px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={approvalByBand} layout="vertical" margin={{ top: 4, right: 40, bottom: 4, left: 8 }}>
                  <CartesianGrid horizontal={false} stroke={CHART.rule} />
                  <XAxis type="number" domain={[0, 1]} axisLine={false} tickLine={false} tick={{ ...CHART.axisTick }} tickFormatter={(v) => `${Math.round(v * 100)}%`} />
                  <YAxis type="category" dataKey="band" axisLine={false} tickLine={false} width={78} tick={{ ...CHART.axisTick }} />
                  <Tooltip contentStyle={tooltipStyle()} cursor={{ fill: "var(--surface-sunk)" }} formatter={(v: number) => pct(v)} />
                  <Bar dataKey="rate" radius={[0, 2, 2, 0]} isAnimationActive={false} label={{ position: "right", formatter: (v: number) => pct(v, 0), fill: "var(--ink-muted)", fontSize: 11, fontFamily: "var(--font-plex-mono)" }}>
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
            <div className="h-[240px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={metrics.override_trend} margin={{ top: 4, right: 12, bottom: 4, left: 0 }}>
                  <CartesianGrid vertical={false} stroke={CHART.rule} />
                  <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ ...CHART.axisTick }} tickFormatter={shortDate} interval="preserveStartEnd" minTickGap={44} />
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
              <div className="flex items-center justify-between">
                <p className="text-label uppercase text-ink-muted">Fairness audit</p>
                <span
                  className={
                    "rounded-sm px-2 py-px text-label uppercase " +
                    (model.fairness_summary.four_fifths_pass
                      ? "bg-band-low-tint text-band-low"
                      : "bg-band-high-tint text-band-high")
                  }
                >
                  {model.fairness_summary.four_fifths_pass
                    ? "Four-fifths rule: pass"
                    : "Four-fifths rule: flagged"}
                </span>
              </div>
              <p className="mt-2 text-body text-ink-muted">
                Approve = score ≥ {model.fairness_summary.approve_min_score}. Portfolio approval{" "}
                {pct(model.fairness_summary.portfolio_approval_rate)}, false-positive rate{" "}
                {pct(model.fairness_summary.portfolio_false_positive_rate)}. Gender and city tier
                pass; the flags below are livelihood groups where genuine cashflow risk lowers
                approval.
              </p>
              {model.fairness_summary.flagged_groups.length ? (
                <table className="mt-3 w-full text-mono-sm">
                  <thead className="text-label uppercase text-ink-faint">
                    <tr>
                      <th className="py-1 text-start font-medium">Flagged group</th>
                      <th className="py-1 text-end font-medium">Approval</th>
                      <th className="py-1 text-end font-medium">Ratio vs best</th>
                      <th className="py-1 text-end font-medium">Observed default</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-rule">
                    {model.fairness_summary.flagged_groups.map((g) => (
                      <tr key={g.dimension + g.group}>
                        <td className="py-1.5 font-sans text-ink">
                          {g.dimension} · {g.group.replace(/_/g, " ")}
                        </td>
                        <td className="py-1.5 text-end tabular-nums text-ink">
                          {pct(g.approval_rate, 0)}
                        </td>
                        <td className="py-1.5 text-end tabular-nums text-band-high">
                          {g.approval_ratio_vs_best.toFixed(2)}
                        </td>
                        <td className="py-1.5 text-end tabular-nums text-ink-muted">
                          {pct(g.observed_default_rate, 0)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : null}
              <p className="mt-2 text-caption text-ink-faint">
                Full audit and mitigations in <code className="font-mono">docs/RESPONSIBLE_AI.md</code>.
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
