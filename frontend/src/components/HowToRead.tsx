"use client";

import { HelpCircle } from "lucide-react";
import { useState } from "react";

const ITEMS: [string, string][] = [
  [
    "Score & band",
    "300–850, higher is safer. LOW 720+ auto-approves, MEDIUM 640–719 goes to manual review, HIGH 560–639 needs a guarantor, VERY_HIGH below 560 is declined with a financial-literacy referral.",
  ],
  [
    "Probability of default (PD)",
    "The calibrated chance this applicant misses repayment — a real frequency, not just a rank. It drives the Qist affordability maths.",
  ],
  [
    "Score ledger",
    "The score derivation as a shopkeeper's khata: opening balance, then each factor as a credit or debit, ending in the closing score. It sums exactly — SHAP values are additive in log-odds and the score is affine in log-odds.",
  ],
  [
    "Safe Qist limit",
    "The affordable monthly installment. The waterfall shows disposable income stepped down by the debt-service cap, a volatility haircut, a data-depth factor and a consistency bonus. Principal follows from the installment and tenor.",
  ],
  [
    "Behavioural radar",
    "Six 0–100 axes for this applicant (solid) against the portfolio median (dashed). It shows where they are unusual, not just how they score.",
  ],
  [
    "Confidence & data gaps",
    "How much the engine trusts this score. A thin file (few months of bills, no transaction log) is imputed at population medians, confidence drops, and the gaps are listed — scoring never fails on partial data.",
  ],
  [
    "What-if analysis",
    "Drag a lever to re-score live, holding everything else constant. Nothing is saved to the application.",
  ],
];

export function HowToRead() {
  const [open, setOpen] = useState(false);
  return (
    <div className="no-print mb-4 rounded-md border border-rule bg-surface">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 px-4 py-2.5 text-body-strong text-ink-muted transition-tokens hover:bg-surface-sunk"
      >
        <HelpCircle size={15} strokeWidth={1.5} />
        How to read this page
        <span className="ms-auto text-caption text-ink-faint">{open ? "hide" : "show"}</span>
      </button>
      {open ? (
        <dl className="grid gap-x-8 gap-y-3 border-t border-rule p-4 sm:grid-cols-2">
          {ITEMS.map(([k, v]) => (
            <div key={k}>
              <dt className="text-body-strong text-ink">{k}</dt>
              <dd className="mt-0.5 text-body text-ink-muted">{v}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </div>
  );
}
