"use client";

import { Printer } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { BAND_META } from "@/lib/utils";
import { fmtDate, pct } from "@/lib/format";
import type { ReasonCode, RiskBand, ScoreResponse } from "@/lib/types";

interface Line {
  description: string;
  urdu?: string;
  credit?: number;
  debit?: number;
}

function buildLines(score: ScoreResponse): Line[] {
  const opening: Line = {
    description: "Opening balance (population base)",
    credit: Math.round(score.base_contribution),
  };
  const sorted = [...score.ledger_lines].sort(
    (a: ReasonCode, b: ReasonCode) =>
      Math.abs(b.impact_points_exact ?? b.impact_points) -
      Math.abs(a.impact_points_exact ?? a.impact_points),
  );
  const contribs: Line[] = sorted
    .filter((c) => c.impact_points !== 0)
    .map((c) => {
      const pts = c.impact_points;
      const clean = c.label_en.replace(/^[+-]?\d+\s*pts\s*—\s*/, "");
      const cleanUr = c.label_ur.replace(/^[+-]?\d+\s*[^\s—]*\s*—\s*/, "");
      return pts > 0
        ? { description: clean, urdu: cleanUr, credit: pts }
        : { description: clean, urdu: cleanUr, debit: -pts };
    });
  return [opening, ...contribs];
}

export function ScoreLedger({
  score,
  applicationRef,
  onPrint,
}: {
  score: ScoreResponse;
  applicationRef: string;
  onPrint?: () => void;
}) {
  const lines = buildLines(score);
  const band = score.risk_band as RiskBand;
  const finalScore = score.score;
  const opening = Math.round(score.base_contribution);

  const [revealed, setRevealed] = useState(lines.length + 1);
  const [running, setRunning] = useState(finalScore);
  const raf = useRef<number>();

  useEffect(() => {
    const reduce =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) {
      setRevealed(lines.length + 1);
      setRunning(finalScore);
      return;
    }
    setRevealed(0);
    setRunning(opening);
    let i = 0;
    const step = () => {
      i += 1;
      setRevealed(i);
      // running total = opening + sum of revealed contribution lines
      const partial = lines.slice(1, i).reduce((acc, l) => acc + (l.credit ?? 0) - (l.debit ?? 0), 0);
      setRunning(i <= 1 ? opening : opening + partial);
      if (i <= lines.length) {
        raf.current = window.setTimeout(step, 90) as unknown as number;
      } else {
        setRunning(finalScore);
      }
    };
    raf.current = window.setTimeout(step, 120) as unknown as number;
    return () => {
      if (raf.current) clearTimeout(raf.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [score.application_id, finalScore]);

  return (
    <div className="rounded-md border border-rule bg-surface">
      <div className="flex items-center justify-between border-b border-rule px-5 py-3">
        <div>
          <p className="font-mono text-h2 font-semibold text-ink">Qist scorecard ledger</p>
          <p className="text-caption text-ink-faint">
            {applicationRef} · {fmtDate(score.scored_at)}
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          className="no-print"
          onClick={() => (onPrint ? onPrint() : window.print())}
        >
          <Printer size={14} strokeWidth={1.5} /> Print credit memo
        </Button>
      </div>

      <div className="overflow-x-auto p-5">
        <table className="w-full min-w-[420px] font-mono text-mono-sm tabular-nums">
          <thead>
            <tr className="text-label uppercase text-ink-muted">
              <th className="border-b-2 border-double border-rule-strong pb-1 text-start font-medium">
                Description
              </th>
              <th className="w-20 border-b-2 border-double border-rule-strong pb-1 pe-2 text-end font-medium">
                Credit
              </th>
              <th className="w-20 border-b-2 border-double border-rule-strong pb-1 text-end font-medium">
                Debit
              </th>
            </tr>
          </thead>
          <tbody className="relative">
            {lines.map((l, idx) => {
              const visible = revealed > idx;
              return (
                <tr
                  key={idx}
                  className="border-b border-rule/70 align-top transition-opacity duration-200"
                  style={{
                    opacity: visible ? 1 : 0,
                    background: idx % 2 === 1 ? "color-mix(in srgb, var(--surface-sunk) 45%, transparent)" : undefined,
                  }}
                >
                  <td className="relative py-1.5 pe-3">
                    {/* the single red column rule */}
                    <span
                      aria-hidden
                      className="absolute end-0 top-0 h-full w-px"
                      style={{ background: "var(--ledger-rule)" }}
                    />
                    <span className="text-ink">{l.description}</span>
                    {l.urdu ? (
                      <span className="urdu block text-caption text-ink-faint">{l.urdu}</span>
                    ) : null}
                  </td>
                  <td className="py-1.5 pe-2 text-end text-ledger-credit">
                    {l.credit !== undefined
                      ? idx === 0
                        ? l.credit
                        : `+${l.credit}`
                      : ""}
                  </td>
                  <td className="py-1.5 text-end text-ledger-debit">
                    {l.debit !== undefined ? `−${l.debit}` : ""}
                  </td>
                </tr>
              );
            })}
            <tr className="border-t-2 border-double border-rule-strong">
              <td className="py-2 text-body-strong uppercase tracking-wide text-ink">Closing score</td>
              <td className="py-2 pe-2 text-end text-body-strong text-ink">{running}</td>
              <td />
            </tr>
          </tbody>
        </table>

        <p className="mt-3 border-t border-double border-rule-strong pt-2 text-body-strong">
          <span className={BAND_META[band].text}>{BAND_META[band].label}</span>
          <span className="text-ink-faint"> · {BAND_META[band].policy} · PD {pct(score.probability_of_default)}</span>
        </p>
        <p className="mt-2 text-caption text-ink-faint">
          The scorecard is affine in log-odds and SHAP values are additive in log-odds, so this
          column sums exactly to the score. Add it up.
        </p>
      </div>

      {/* screen-reader table of the same numbers */}
      <table className="sr-only">
        <caption>Score derivation</caption>
        <tbody>
          {lines.map((l, i) => (
            <tr key={i}>
              <td>{l.description}</td>
              <td>{l.credit ?? -(l.debit ?? 0)}</td>
            </tr>
          ))}
          <tr>
            <td>Closing score</td>
            <td>{finalScore}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
