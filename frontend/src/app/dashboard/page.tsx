"use client";

import { useEffect, useState } from "react";
import { ApplicationTable } from "@/components/ApplicationTable";
import { KpiRow, KpiStat } from "@/components/KpiStat";
import { BackendBanner } from "@/components/ui/BackendBanner";
import { Disclaimer } from "@/components/ui/Disclaimer";
import { SkeletonRows } from "@/components/ui/Skeleton";
import { cn } from "@/lib/utils";
import { pkr } from "@/lib/format";
import { api, ApiError } from "@/lib/api";
import { DEMO_MODE, MOCK_BUNDLES } from "@/lib/mockProfiles";
import type {
  ApplicationSummary,
  MetricsResponse,
  PaginatedApplications,
  RiskBand,
} from "@/lib/types";

const BANDS: RiskBand[] = ["LOW", "MEDIUM", "HIGH", "VERY_HIGH"];
const CITIES = [
  "Karachi", "Lahore", "Faisalabad", "Rawalpindi", "Multan",
  "Peshawar", "Quetta", "Hyderabad", "Sialkot", "Gujranwala",
];

function demoRows(): ApplicationSummary[] {
  return MOCK_BUNDLES.map((b, i) => ({
    id: b.profile.id,
    applicant_name: b.profile.applicant.full_name,
    city: b.profile.city,
    archetype: b.profile.archetype,
    status: "SCORED",
    requested_amount_pkr: b.profile.requested_amount_pkr,
    score: b.score.score,
    risk_band: b.score.risk_band,
    safe_installment_pkr: b.score.qist_limit.safe_installment_pkr || null,
    principal_pkr: b.score.qist_limit.principal_pkr || null,
    submitted_at: new Date(Date.now() - i * 3600_000).toISOString(),
    decided_at: null,
    override_flag: false,
  }));
}

export default function DashboardPage() {
  const [rows, setRows] = useState<ApplicationSummary[] | null>(null);
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
  const [offline, setOffline] = useState(false);
  const [band, setBand] = useState<RiskBand | "">("");
  const [city, setCity] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [list, m]: [PaginatedApplications, MetricsResponse] = await Promise.all([
          api.listApplications({ risk_band: band || undefined, city: city || undefined, page_size: 100 }),
          api.metrics(),
        ]);
        if (cancelled) return;
        setRows(list.items);
        setMetrics(m);
        setOffline(false);
      } catch (e) {
        if (cancelled) return;
        if (e instanceof ApiError && e.offline) {
          setOffline(true);
          if (DEMO_MODE) {
            const dr = demoRows().filter(
              (r) => (!band || r.risk_band === band) && (!city || r.city === city),
            );
            setRows(dr);
          } else {
            setRows([]);
          }
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [band, city]);

  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between">
        <h1 className="text-h1 text-ink">Underwriting queue</h1>
        <span className="text-mono-sm text-ink-faint">{rows?.length ?? 0} applications</span>
      </div>
      <p className="mb-5 text-caption text-ink-faint">
        Click any row to open the applicant. The top six are the demo profiles — start with one of
        those.
      </p>

      {offline && <BackendBanner demoActive={DEMO_MODE} />}

      <KpiRow>
        <KpiStat label="Applications today" value={String(metrics?.applications_today ?? "—")} />
        <KpiStat
          label="Approval rate"
          value={metrics ? `${(metrics.approval_rate * 100).toFixed(1)}%` : "—"}
        />
        <KpiStat label="Mean score" value={metrics ? metrics.mean_score.toFixed(0) : "—"} />
        <KpiStat
          label="Portfolio expected loss"
          value={metrics ? pkr(metrics.portfolio_expected_loss_pkr, { compact: true }) : "—"}
        />
        <KpiStat
          label="Override rate"
          value={metrics ? `${(metrics.override_rate * 100).toFixed(1)}%` : "—"}
          delta={
            metrics
              ? { text: "governance metric", direction: "flat", tone: "medium" }
              : undefined
          }
        />
      </KpiRow>

      <div className="my-4 flex flex-wrap items-center gap-2">
        <span className="text-label uppercase text-ink-muted">Band</span>
        {(["", ...BANDS] as const).map((b) => (
          <button
            key={b || "all"}
            onClick={() => setBand(b)}
            className={cn(
              "rounded-sm px-2.5 py-1 text-body-strong transition-tokens",
              band === b ? "bg-brand text-white" : "bg-surface-sunk text-ink-muted hover:bg-brand-tint",
            )}
          >
            {b === "" ? "All" : b.replace("_", " ")}
          </button>
        ))}
        <span className="ms-4 text-label uppercase text-ink-muted">City</span>
        <select
          value={city}
          onChange={(e) => setCity(e.target.value)}
          className="h-8 rounded-sm border border-rule-strong bg-surface px-2 text-body"
        >
          <option value="">All cities</option>
          {CITIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </div>

      {rows === null ? <SkeletonRows rows={8} /> : <ApplicationTable rows={rows} />}

      <Disclaimer className="mt-5" />
    </div>
  );
}
