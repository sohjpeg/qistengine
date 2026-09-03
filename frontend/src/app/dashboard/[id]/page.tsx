"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft } from "lucide-react";
import { BehaviorRadar } from "@/components/BehaviorRadar";
import { CashflowChart } from "@/components/CashflowChart";
import { DecisionPanel } from "@/components/DecisionPanel";
import { QistLimitCard } from "@/components/QistLimitCard";
import { ReasonCodeColumns } from "@/components/ReasonCodeList";
import { RiskBadge } from "@/components/RiskBadge";
import { ScoreGauge } from "@/components/ScoreGauge";
import { ScoreLedger } from "@/components/ScoreLedger";
import { BackendBanner } from "@/components/ui/BackendBanner";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { Disclaimer } from "@/components/ui/Disclaimer";
import { Skeleton } from "@/components/ui/Skeleton";
import { Tab, TabList, TabPanel, Tabs } from "@/components/ui/Tabs";
import { fmtDate, pct, pkr } from "@/lib/format";
import { api, ApiError } from "@/lib/api";
import { DEMO_MODE, MOCK_BUNDLES } from "@/lib/mockProfiles";
import type { ApplicationDetail } from "@/lib/types";

function demoDetail(id: string): ApplicationDetail | null {
  const b = MOCK_BUNDLES.find((x) => x.profile.id === id);
  if (!b) return null;
  return {
    id,
    status: "SCORED",
    requested_amount_pkr: b.profile.requested_amount_pkr,
    purpose: b.profile.purpose,
    submitted_at: new Date().toISOString(),
    decided_at: null,
    decided_by: null,
    applicant: {
      id: "demo",
      full_name: b.profile.applicant.full_name,
      cnic_masked: "*****-*******-*",
      phone_masked: "**********",
      city: b.profile.city,
      archetype: b.profile.archetype,
      business_type: b.profile.business_type,
      dependents_count: b.profile.applicant.dependents_count,
      has_fixed_premises: b.profile.applicant.has_fixed_premises,
      created_at: new Date().toISOString(),
    },
    documents: [],
    score_result: b.score,
    decision: null,
  };
}

export default function ApplicationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<ApplicationDetail | null>(null);
  const [offline, setOffline] = useState(false);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const d = await api.getApplication(id);
        if (!cancelled) setDetail(d);
      } catch (e) {
        if (cancelled) return;
        if (e instanceof ApiError && e.offline && DEMO_MODE) {
          const d = demoDetail(id);
          if (d) {
            setDetail(d);
            setOffline(true);
          } else setNotFound(true);
        } else if (e instanceof ApiError && e.status === 404) {
          setNotFound(true);
        } else {
          setOffline(true);
          const d = demoDetail(id);
          if (d) setDetail(d);
          else setNotFound(true);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (notFound) {
    return (
      <div className="mx-auto max-w-lg py-16 text-center">
        <p className="text-h1 text-ink">Application not found</p>
        <p className="mt-2 text-body text-ink-muted">
          It may have been created in a previous session.{" "}
          <Link href="/dashboard" className="text-brand underline">
            Back to the queue
          </Link>
          .
        </p>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="grid gap-6 lg:grid-cols-12">
        <Skeleton className="h-64 lg:col-span-12" />
        <Skeleton className="h-96 lg:col-span-5" />
        <Skeleton className="h-96 lg:col-span-7" />
      </div>
    );
  }

  const score = detail.score_result;
  const isUuid = /^[0-9a-f]{8}-[0-9a-f]{4}-/i.test(detail.id);
  const ref = isUuid
    ? `APP-${detail.id.slice(0, 8).toUpperCase()}`
    : `APP-${detail.id.split("-")[0].toUpperCase()}`;

  return (
    <div className="print-page">
      <div className="no-print mb-4 flex items-center justify-between">
        <Link href="/dashboard" className="inline-flex items-center gap-1 text-body-strong text-brand">
          <ArrowLeft size={15} /> Queue
        </Link>
        <span className="text-mono-sm text-ink-faint">{ref}</span>
      </div>

      {offline && <BackendBanner demoActive={DEMO_MODE} />}

      <header className="mb-5 flex flex-wrap items-baseline justify-between gap-2 border-b border-rule-strong pb-3">
        <div>
          <h1 className="print-serif text-h1 text-ink">{detail.applicant.full_name}</h1>
          <p className="text-body text-ink-muted">
            {detail.applicant.business_type} · {detail.applicant.city} ·{" "}
            {detail.applicant.archetype.replace(/_/g, " ")} · CNIC {detail.applicant.cnic_masked}
          </p>
        </div>
        <p className="font-mono text-mono-sm text-ink-faint">
          Requested {pkr(detail.requested_amount_pkr)} · {detail.purpose} · submitted{" "}
          {fmtDate(detail.submitted_at)}
        </p>
      </header>

      {!score ? (
        <Card>
          <CardBody>This application has not been scored.</CardBody>
        </Card>
      ) : (
        <>
          <ScoreLedger score={score} applicationRef={ref} />

          {score.data_gaps.length ? (
            <div className="mt-4 rounded-sm bg-band-medium-tint px-3 py-2 text-caption text-band-medium">
              Partial data — {score.data_gaps.map((g) => g.detail).join(" ")} Confidence{" "}
              {pct(score.confidence, 0)}.
            </div>
          ) : null}

          <div className="mt-6 grid items-start gap-6 lg:grid-cols-12">
            {/* left column */}
            <div className="flex flex-col gap-6 lg:col-span-5">
              <Card>
                <CardBody className="flex flex-col items-center gap-2">
                  <ScoreGauge score={score.score} band={score.risk_band} size="lg" animate />
                  <RiskBadge band={score.risk_band} />
                  <p className="text-center text-caption text-ink-faint">
                    {score.band_label} · PD {pct(score.probability_of_default)}
                    <br />
                    confidence {pct(score.confidence, 0)} · model {score.model_version}
                  </p>
                </CardBody>
              </Card>

              <QistLimitCard limit={score.qist_limit} />

              {score.adverse_action_codes.length ? (
                <Card>
                  <CardHeader>
                    <CardTitle>Adverse action notice</CardTitle>
                  </CardHeader>
                  <CardBody className="print-serif">
                    <p className="text-body text-ink-muted">
                      This demonstration decision was influenced primarily by:
                    </p>
                    <ul className="mt-2 space-y-1 font-mono text-mono-sm text-ink">
                      {score.adverse_action_codes.map((c) => (
                        <li key={c}>· {c}</li>
                      ))}
                    </ul>
                  </CardBody>
                </Card>
              ) : null}

              <div className="no-print">
                <DecisionPanel application={detail} score={score} onDecided={setDetail} />
              </div>
            </div>

            {/* right column */}
            <div className="flex flex-col gap-6 lg:col-span-7">
              <Card>
                <CardHeader>
                  <CardTitle>Behavioural profile</CardTitle>
                </CardHeader>
                <CardBody>
                  <BehaviorRadar
                    applicant={score.behavioral_metrics}
                    portfolioMedian={score.portfolio_median_metrics}
                  />
                </CardBody>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Reason codes</CardTitle>
                </CardHeader>
                <CardBody>
                  <ReasonCodeColumns codes={score.reason_codes} />
                </CardBody>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Cashflow</CardTitle>
                </CardHeader>
                <CardBody>
                  <CashflowChart series={score.monthly_series} />
                </CardBody>
              </Card>
            </div>
          </div>

          <Card className="mt-6 no-print">
            <CardHeader>
              <CardTitle>Documents</CardTitle>
            </CardHeader>
            <CardBody>
              {detail.documents.length ? (
                <Tabs defaultValue={detail.documents[0].id}>
                  <TabList>
                    {detail.documents.map((d) => (
                      <Tab key={d.id} value={d.id}>
                        {d.doc_type.replace(/_/g, " ")}
                      </Tab>
                    ))}
                  </TabList>
                  {detail.documents.map((d) => (
                    <TabPanel key={d.id} value={d.id} className="pt-3">
                      <p className="mb-2 text-caption text-ink-faint">
                        {d.filename} · {d.extraction_method} · confidence {pct(d.confidence, 0)}
                      </p>
                      <dl className="grid gap-x-8 gap-y-1 font-mono text-mono-sm sm:grid-cols-2 lg:grid-cols-3">
                        {Object.entries(d.extracted_json).map(([k, v]) => (
                          <div key={k} className="flex justify-between border-b border-rule py-1">
                            <dt className="text-ink-muted">{k}</dt>
                            <dd className="text-ink">{String(v)}</dd>
                          </div>
                        ))}
                      </dl>
                    </TabPanel>
                  ))}
                </Tabs>
              ) : (
                <p className="text-body text-ink-muted">
                  No documents attached to this application.
                </p>
              )}
            </CardBody>
          </Card>

          <Disclaimer className="mt-6" />
          <div className="print-footer">
            {ref} · {score.model_version} · score {score.score} · PD{" "}
            {pct(score.probability_of_default)} · {fmtDate(score.scored_at)} · Demonstration model on
            synthetic data — not a regulated credit decision.
          </div>
        </>
      )}
    </div>
  );
}
