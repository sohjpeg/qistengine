import Link from "next/link";
import { ArrowRight, FileText, Gauge, Stamp } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Disclaimer } from "@/components/ui/Disclaimer";

const STEPS = [
  {
    icon: FileText,
    title: "Ingest",
    body: "One electricity bill and one wallet transaction log. OCR reads the bill; the parser normalises any wallet export — JazzCash, EasyPaisa, a hand-kept Digital Khata.",
  },
  {
    icon: Gauge,
    title: "Score",
    body: "26 behavioural features, a calibrated LightGBM scorecard, and a 300–850 score with a probability of default that is a real probability.",
  },
  {
    icon: Stamp,
    title: "Decide",
    body: "A safe monthly Qist, an exact reason-code ledger, an adverse-action notice, and a printable credit memo for the branch file.",
  },
];

export default function LandingPage() {
  return (
    <div className="mx-auto max-w-4xl">
      <p className="text-label uppercase text-ink-muted">Alternative credit scoring · Pakistan</p>
      <h1 className="mt-3 text-display text-ink">
        Around 100 million adults in Pakistan sit outside the formal banking system. A shopkeeper
        with twelve years of trading history still has no credit file.
      </h1>
      <p className="mt-4 max-w-2xl text-body text-ink-muted">
        Traditional bureau scoring needs a loan history that unbanked merchants and daily-wage
        earners were never allowed to build. QistEngine scores the data they do generate — utility
        payments and mobile-wallet cashflow — and turns it into a defensible installment offer.
      </p>

      <div className="mt-6 flex gap-3">
        <Link href="/apply">
          <Button>
            Open the applicant portal <ArrowRight size={15} />
          </Button>
        </Link>
        <Link href="/dashboard">
          <Button variant="secondary">Go to the underwriting queue</Button>
        </Link>
      </div>

      <div className="mt-10 grid gap-px overflow-hidden rounded-md border border-rule bg-rule sm:grid-cols-3">
        {STEPS.map((s) => (
          <div key={s.title} className="bg-surface p-5">
            <s.icon size={18} strokeWidth={1.5} className="text-brand" aria-hidden />
            <p className="mt-2 text-h2 text-ink">{s.title}</p>
            <p className="mt-1 text-body text-ink-muted">{s.body}</p>
          </div>
        ))}
      </div>

      <Disclaimer className="mt-8" />
    </div>
  );
}
