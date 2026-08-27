"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { pkr } from "@/lib/format";
import type { QistLimit } from "@/lib/types";

const TENORS = [3, 6, 9, 12] as const;
const MARKUP = 0.015;

/** Recompute principal client-side from the returned components — no network call. */
function principalFor(installment: number, tenor: number) {
  const gross = installment * tenor;
  return Math.floor(gross / (1 + MARKUP * tenor) / 1000) * 1000;
}

export function QistLimitCard({ limit }: { limit: QistLimit }) {
  const [tenor, setTenor] = useState<number>(limit.tenor_months);

  if (!limit.eligible) {
    return (
      <div className="rounded-md border border-rule bg-surface p-5">
        <p className="text-label uppercase text-ink-muted">Safe Qist limit</p>
        <p className="mt-2 text-h2 text-band-high">Not eligible at this time</p>
        <p className="mt-1 text-body text-ink-muted">
          Disposable income is below the minimum installment of {pkr(2000)}. Reason code:{" "}
          <code className="font-mono text-mono-sm">{limit.reason}</code>. A financial-literacy
          referral is offered on decline.
        </p>
      </div>
    );
  }

  const installment = limit.safe_installment_pkr;
  const principal = principalFor(installment, tenor);
  const totalRepayable = installment * tenor;

  const b = limit.breakdown;
  const disposable = b.disposable_income_pkr;
  const steps = [
    { label: `DSR cap ×${b.dsr_cap.toFixed(2)}`, factor: b.dsr_cap },
    { label: `Volatility haircut ×${b.volatility_haircut.toFixed(2)}`, factor: b.volatility_haircut },
    { label: `Data-depth ×${b.depth_confidence.toFixed(2)}`, factor: b.depth_confidence },
    { label: `Consistency bonus ×${b.consistency_bonus.toFixed(2)}`, factor: b.consistency_bonus },
  ];
  let runningValue = disposable;
  const waterfall = steps.map((s) => {
    const before = runningValue;
    runningValue = before * s.factor;
    return { ...s, before, after: runningValue, removed: before - runningValue };
  });
  const maxVal = Math.max(disposable, 1);

  return (
    <div className="rounded-md border border-rule bg-surface p-5">
      <p className="text-label uppercase text-ink-muted">Safe Qist — monthly installment</p>
      <p className="mt-1 flex items-baseline gap-2">
        <span className="text-h2 text-ink-muted">Rs</span>
        <span className="font-mono text-score-hero tabular-nums text-ink">
          {installment.toLocaleString("en-PK")}
        </span>
      </p>
      <p className="mt-1 font-mono text-figure text-ink-muted">
        Principal {pkr(principal)} · {tenor} months · flat markup {(MARKUP * 100).toFixed(1)}%/mo ·
        total repayable {pkr(totalRepayable)}
      </p>

      <div className="mt-4 flex items-center gap-2">
        <span className="text-label uppercase text-ink-muted">Tenor</span>
        {TENORS.map((t) => (
          <button
            key={t}
            onClick={() => setTenor(t)}
            className={cn(
              "h-[30px] rounded-sm px-2.5 font-mono text-mono-sm tabular-nums transition-tokens",
              t === tenor
                ? "bg-brand text-white"
                : "bg-surface-sunk text-ink-muted hover:bg-brand-tint",
            )}
          >
            {t}m
          </button>
        ))}
      </div>

      <div className="mt-5">
        <p className="mb-2 text-label uppercase text-ink-muted">
          How {pkr(disposable)} disposable income becomes the offer
        </p>
        <div className="space-y-1.5">
          <WaterfallBar label="Disposable income" value={disposable} max={maxVal} solid />
          {waterfall.map((w) => (
            <WaterfallBar
              key={w.label}
              label={w.label}
              value={w.after}
              max={maxVal}
              note={w.removed >= 0 ? `−${pkr(w.removed)}` : `+${pkr(-w.removed)}`}
            />
          ))}
          <WaterfallBar label="Rounded to Rs 500" value={installment} max={maxVal} solid />
        </div>
      </div>
    </div>
  );
}

function WaterfallBar({
  label,
  value,
  max,
  note,
  solid,
}: {
  label: string;
  value: number;
  max: number;
  note?: string;
  solid?: boolean;
}) {
  const w = Math.max(2, (value / max) * 100);
  return (
    <div className="flex items-center gap-3">
      <span className="w-40 shrink-0 text-caption text-ink-muted">{label}</span>
      <div className="relative h-4 flex-1 rounded-sm bg-surface-sunk">
        <div
          className="h-4 rounded-sm"
          style={{
            width: `${w}%`,
            background: solid ? "var(--brand)" : "color-mix(in srgb, var(--brand) 35%, var(--surface))",
          }}
        />
      </div>
      <span className="w-28 shrink-0 text-end font-mono text-mono-sm tabular-nums text-ink">
        {pkr(value)}
      </span>
      {note ? <span className="w-24 shrink-0 text-end text-caption text-ink-faint">{note}</span> : <span className="w-24 shrink-0" />}
    </div>
  );
}
