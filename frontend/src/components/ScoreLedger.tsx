"use client";

import { Printer } from "lucide-react";
import { useEffect, useState } from "react";
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

const MAX_LINES = 9; // material factors shown; the long tail folds into one row

function buildLines(score: ScoreResponse): Line[] {
  const opening = Math.round(score.base_contribution);
  const lines: Line[] = [
    { description: "Opening balance (population base)", credit: opening },
  ];

  const sorted = [...score.ledger_lines]
    .filter((c) => c.impact_points !== 0)
    .sort((a, b) => Math.abs(b.impact_points) - Math.abs(a.impact_points));

  const toLine = (c: ReasonCode): Line => {
    const pts = c.impact_points;
    const clean = c.label_en.replace(/^[+-]?\d+\s*pts\s*—\s*/, "");
    const cleanUr = c.label_ur.replace(/^[+-]?\d+\s*[^\s—]*\s*—\s*/, "");
    return pts > 0
      ? { description: clean, urdu: cleanUr, credit: pts }
      : { description: clean, urdu: cleanUr, debit: -pts };
  };

  const head = sorted.slice(0, MAX_LINES);
  const tail = sorted.slice(MAX_LINES);
  head.forEach((c) => lines.push(toLine(c)));

  if (tail.length) {
    const net = tail.reduce((acc, c) => acc + c.impact_points, 0);
    if (net !== 0) {
      lines.push({
        description: `${tail.length} smaller factors`,
        credit: net > 0 ? net : undefined,
        debit: net < 0 ? -net : undefined,
      });
    } else {
      lines.push({ description: `${tail.length} smaller factors (net 0)`, credit: 0 });
    }
  }

  // Reconcile: the score is rounded/clipped, so a small residual line makes the
  // visible column sum exactly to the closing score.
  const shownSum = lines.reduce((acc, l) => acc + (l.credit ?? 0) - (l.debit ?? 0), 0);
  const residual = score.score - shownSum;
  if (residual !== 0) {
    lines.push({
      description: "Rounding to nearest point",
      credit: residual > 0 ? residual : undefined,
      debit: residual < 0 ? -residual : undefined,
    });
  }
  return lines;
}

const STAGGER_MS = 70;

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
  const total = lines.length;

  // Closing-score count-up: one bounded rAF loop, never a per-line timer.
  const [running, setRunning] = useState(finalScore);
  useEffect(() => {
    if (
      typeof window === "undefined" ||
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ) {
      setRunning(finalScore);
      return;
    }
    const duration = Math.min(1100, 200 + total * STAGGER_MS);
    const start = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      setRunning(Math.round(opening + (finalScore - opening) * eased));
      if (p < 1) raf = requestAnimationFrame(tick);
      else setRunning(finalScore);
    };
    setRunning(opening);
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [score.application_id, finalScore]);

  const visible = lines;

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
          <tbody>
            {visible.map((l, idx) => (
              <tr
                key={idx}
                className="ledger-row border-b border-rule/70 align-top"
                style={{
                  animationDelay: `${idx * STAGGER_MS}ms`,
                  background:
                    idx % 2 === 1 ? "var(--surface-sunk)" : undefined,
                }}
              >
                <td className="relative py-1.5 pe-3">
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
            ))}
            <tr className="border-t-2 border-double border-rule-strong">
              <td className="py-2 text-body-strong uppercase tracking-wide text-ink">
                Closing score
              </td>
              <td className="py-2 pe-2 text-end text-body-strong text-ink">{running}</td>
              <td />
            </tr>
          </tbody>
        </table>

        <p className="mt-3 border-t border-double border-rule-strong pt-2 text-body-strong">
          <span className={BAND_META[band].text}>{BAND_META[band].label}</span>
          <span className="text-ink-faint">
            {" "}
            · {BAND_META[band].policy} · PD {pct(score.probability_of_default)}
          </span>
        </p>
        <p className="mt-2 text-caption text-ink-faint">
          The scorecard is affine in log-odds and SHAP values are additive in log-odds, so this
          column sums exactly to the score. Add it up.
        </p>
      </div>

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
