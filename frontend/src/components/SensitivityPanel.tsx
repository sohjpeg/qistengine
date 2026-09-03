"use client";

import { RotateCcw } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { RiskBadge } from "@/components/RiskBadge";
import { api, ApiError } from "@/lib/api";
import { BAND_HEX } from "@/lib/utils";
import { pct, pkr, signedPts } from "@/lib/format";
import type { ScoreResponse } from "@/lib/types";

/** The four levers an officer reasons about, mapped onto model features. */
interface Lever {
  key: string;
  label: string;
  hint: string;
  /** slider domain in display units */
  min: (base: number) => number;
  max: (base: number) => number;
  step: number;
  /** feature value -> slider display value */
  toDisplay: (v: number) => number;
  /** slider display value -> feature value */
  toFeature: (d: number) => number;
  format: (d: number) => string;
  /** which direction is "better" for the applicant — drives the arrow colour */
  higherIsBetter: boolean;
}

const LEVERS: Lever[] = [
  {
    key: "monthly_inflow_pkr",
    label: "Monthly income",
    hint: "recorded wallet inflow",
    min: (b) => Math.max(10000, Math.round((b * 0.5) / 1000) * 1000),
    max: (b) => Math.round((b * 1.6) / 1000) * 1000,
    step: 1000,
    toDisplay: (v) => v,
    toFeature: (d) => d,
    format: (d) => pkr(d),
    higherIsBetter: true,
  },
  {
    key: "utility_on_time_ratio",
    label: "Utility bills paid on time",
    hint: "share of the last 12 bills",
    min: () => 0,
    max: () => 100,
    step: 1,
    toDisplay: (v) => Math.round(v * 100),
    toFeature: (d) => d / 100,
    format: (d) => `${d}%`,
    higherIsBetter: true,
  },
  {
    key: "cashflow_volatility",
    label: "Income volatility",
    hint: "month-to-month swing",
    min: () => 10,
    max: () => 110,
    step: 1,
    toDisplay: (v) => Math.round(v * 100),
    toFeature: (d) => d / 100,
    format: (d) => `${d}%`,
    higherIsBetter: false,
  },
  {
    key: "expense_to_income_ratio",
    label: "Expense burden",
    hint: "essential spend vs income",
    min: () => 40,
    max: () => 140,
    step: 1,
    toDisplay: (v) => Math.round(v * 100),
    toFeature: (d) => d / 100,
    format: (d) => `${d}%`,
    higherIsBetter: false,
  },
];

function clamp(v: number, lo: number, hi: number) {
  return Math.min(hi, Math.max(lo, v));
}

export function SensitivityPanel({ baseline }: { baseline: ScoreResponse }) {
  const baseFeatures = baseline.features_used;

  const bounds = useMemo(
    () =>
      LEVERS.map((l) => {
        const baseVal = l.toDisplay(baseFeatures[l.key] ?? 0);
        return { lo: l.min(baseVal), hi: l.max(baseVal), base: baseVal };
      }),
    [baseFeatures],
  );

  const initial = useMemo(
    () => LEVERS.map((l, i) => clamp(l.toDisplay(baseFeatures[l.key] ?? 0), bounds[i].lo, bounds[i].hi)),
    [baseFeatures, bounds],
  );

  const [values, setValues] = useState<number[]>(initial);
  const [result, setResult] = useState<ScoreResponse>(baseline);
  const [busy, setBusy] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout>>();
  const seq = useRef(0);

  const dirty = values.some((v, i) => v !== initial[i]);

  const rescore = useCallback(
    (next: number[]) => {
      const features: Record<string, number> = { ...baseFeatures };
      LEVERS.forEach((l, i) => {
        features[l.key] = l.toFeature(next[i]);
      });
      // keep net_cashflow_ratio consistent with the income lever
      if (features.monthly_outflow_pkr != null && features.monthly_inflow_pkr > 0) {
        features.net_cashflow_ratio = clamp(
          (features.monthly_inflow_pkr - features.monthly_outflow_pkr) / features.monthly_inflow_pkr,
          -0.6,
          0.8,
        );
      }
      const mySeq = ++seq.current;
      setBusy(true);
      api
        .score({ features, archetype_hint: baseline.archetype_hint ?? undefined })
        .then((r) => {
          if (mySeq === seq.current) {
            setResult(r);
            setUnavailable(false);
          }
        })
        .catch((e) => {
          if (mySeq === seq.current && e instanceof ApiError) setUnavailable(true);
        })
        .finally(() => {
          if (mySeq === seq.current) setBusy(false);
        });
    },
    [baseFeatures, baseline.archetype_hint],
  );

  useEffect(() => {
    if (!dirty) {
      setResult(baseline);
      return;
    }
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => rescore(values), 320);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [values]);

  function reset() {
    seq.current++;
    setValues(initial);
    setResult(baseline);
    setBusy(false);
  }

  const scoreDelta = result.score - baseline.score;
  const hex = BAND_HEX[result.risk_band];
  const baseInstallment = baseline.qist_limit.eligible ? baseline.qist_limit.safe_installment_pkr : 0;
  const nowInstallment = result.qist_limit.eligible ? result.qist_limit.safe_installment_pkr : 0;
  const instDelta = nowInstallment - baseInstallment;

  return (
    <div className="no-print rounded-md border border-rule bg-surface">
      <div className="flex items-center justify-between border-b border-rule px-5 py-3">
        <div>
          <h2 className="text-h2 text-ink">What-if analysis</h2>
          <p className="text-caption text-ink-faint">
            Move a lever to see the model re-score live, holding everything else constant.
          </p>
        </div>
        <button
          onClick={reset}
          disabled={!dirty}
          className="inline-flex items-center gap-1.5 rounded-sm border border-rule-strong bg-surface px-3 py-1.5 text-body-strong text-ink-muted transition-tokens hover:bg-surface-sunk disabled:opacity-40"
        >
          <RotateCcw size={13} strokeWidth={1.5} /> Reset to actual
        </button>
      </div>

      <div className="grid gap-6 p-5 lg:grid-cols-[1.15fr_1fr]">
        {/* levers */}
        <div className="flex flex-col gap-4">
          {LEVERS.map((l, i) => {
            const b = bounds[i];
            const changed = values[i] !== initial[i];
            return (
              <div key={l.key}>
                <div className="flex items-baseline justify-between">
                  <label htmlFor={`lever-${l.key}`} className="text-body-strong text-ink">
                    {l.label}
                    <span className="ms-2 text-caption font-normal text-ink-faint">{l.hint}</span>
                  </label>
                  <span
                    className="font-mono text-figure tabular-nums"
                    style={{ color: changed ? "var(--brand)" : "var(--ink)" }}
                  >
                    {l.format(values[i])}
                  </span>
                </div>
                <input
                  id={`lever-${l.key}`}
                  type="range"
                  min={b.lo}
                  max={b.hi}
                  step={l.step}
                  value={values[i]}
                  onChange={(e) => {
                    const next = [...values];
                    next[i] = Number(e.target.value);
                    setValues(next);
                  }}
                  className="mt-2 h-1.5 w-full cursor-pointer appearance-none rounded-sm bg-surface-sunk accent-brand"
                  aria-valuetext={l.format(values[i])}
                />
                <div className="mt-1 flex justify-between text-mono-sm text-ink-faint">
                  <span>{l.format(b.lo)}</span>
                  <span>actual {l.format(b.base)}</span>
                  <span>{l.format(b.hi)}</span>
                </div>
              </div>
            );
          })}
        </div>

        {/* live result */}
        <div className="rounded-md border border-rule bg-surface-sunk p-4" aria-live="polite">
          {unavailable ? (
            <p className="text-body text-band-high">
              Live re-scoring needs the backend running. Start it with{" "}
              <code className="font-mono text-mono-sm">uvicorn app.main:app --reload</code>.
            </p>
          ) : (
            <div className={busy ? "opacity-60 transition-opacity" : "transition-opacity"}>
              <p className="text-label uppercase text-ink-muted">
                {dirty ? "Modelled score" : "Actual score"}
              </p>
              <div className="mt-1 flex items-baseline gap-3">
                <span className="font-mono text-score-hero tabular-nums" style={{ color: hex }}>
                  {result.score}
                </span>
                {dirty && scoreDelta !== 0 ? (
                  <span
                    className="font-mono text-figure tabular-nums"
                    style={{ color: scoreDelta > 0 ? "var(--ledger-credit)" : "var(--ledger-debit)" }}
                  >
                    {signedPts(scoreDelta)} vs {baseline.score}
                  </span>
                ) : null}
              </div>
              <div className="mt-2">
                <RiskBadge band={result.risk_band} />
              </div>

              <dl className="mt-4 space-y-1.5 border-t border-rule pt-3 font-mono text-mono-sm">
                <Row
                  k="Probability of default"
                  v={pct(result.probability_of_default)}
                  delta={
                    dirty
                      ? `${result.probability_of_default > baseline.probability_of_default ? "▲" : "▼"} ${pct(
                          Math.abs(result.probability_of_default - baseline.probability_of_default),
                        )}`
                      : undefined
                  }
                  deltaBad={result.probability_of_default > baseline.probability_of_default}
                />
                <Row
                  k="Safe Qist installment"
                  v={result.qist_limit.eligible ? `${pkr(nowInstallment)}/mo` : "not eligible"}
                  delta={
                    dirty && instDelta !== 0
                      ? `${instDelta > 0 ? "▲" : "▼"} ${pkr(Math.abs(instDelta))}`
                      : undefined
                  }
                  deltaBad={instDelta < 0}
                />
                <Row
                  k="Principal offered"
                  v={result.qist_limit.eligible ? pkr(result.qist_limit.principal_pkr) : "—"}
                />
              </dl>

              <p className="mt-3 text-caption text-ink-faint">
                {dirty
                  ? "Hypothetical — not saved to the application."
                  : "Drag any lever above to model a change."}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Row({
  k,
  v,
  delta,
  deltaBad,
}: {
  k: string;
  v: string;
  delta?: string;
  deltaBad?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between">
      <dt className="font-sans text-body text-ink-muted">{k}</dt>
      <dd className="flex items-baseline gap-2 text-ink">
        <span className="tabular-nums">{v}</span>
        {delta ? (
          <span
            className="text-mono-sm tabular-nums"
            style={{ color: deltaBad ? "var(--ledger-debit)" : "var(--ledger-credit)" }}
          >
            {delta}
          </span>
        ) : null}
      </dd>
    </div>
  );
}
