import Link from "next/link";
import Image from "next/image";
import { ArrowRight, FileText, Gauge, Stamp } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Disclaimer } from "@/components/ui/Disclaimer";

const CREATORS = [
  {
    name: "Sohaib Amir Bukhari",
    role: "BS Computer Science · NUST",
    photo: "/team/sohaib.jpg",
    linkedin: "https://www.linkedin.com/in/sohaib-amir-7a89161a6/",
  },
  {
    name: "Asma Imran",
    role: "BS Computer Science · NUST",
    photo: "/team/asma.jpg",
    linkedin: "https://www.linkedin.com/in/asmaimran/",
  },
];

const STEPS = [
  {
    icon: FileText,
    title: "Ingest",
    body: "A utility bill and a wallet statement — PDF or CSV. pdfplumber reads the bill's text layer (Tesseract for scans); the statement parser handles JazzCash, EasyPaisa or a hand-kept Digital Khata — tolerant of preamble rows, split debit/credit columns, and Rs/comma formatting, with Urdu-and-English transaction classification. Unreadable input falls back to a clearly-labelled simulated extraction.",
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

const TOUR = [
  {
    n: "1",
    head: "Score an applicant",
    body: "Open the applicant portal and click a Quick Demo profile — Bilal is a good first look. It fills the form; hit Submit application.",
    href: "/apply",
    cta: "Open the applicant portal",
  },
  {
    n: "2",
    head: "Read the decision",
    body: "You land on the applicant page: the score ledger (it foots exactly to the score), the safe monthly Qist with its haircut waterfall, and the behavioural radar. Drag a slider in What-if analysis to re-score live.",
    href: "/dashboard/bilal-karachi-kiryana",
    cta: "Jump straight to Bilal",
  },
  {
    n: "3",
    head: "See the portfolio & the model",
    body: "The underwriting queue lists every applicant; the analytics page shows the model card (AUC, KS, Gini) and the fairness audit that flags the model's own disparate impact.",
    href: "/analytics",
    cta: "Open portfolio analytics",
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

      <div className="mt-6 flex flex-wrap gap-3">
        <Link href="/apply">
          <Button>
            Open the applicant portal <ArrowRight size={15} />
          </Button>
        </Link>
        <Link href="/dashboard">
          <Button variant="secondary">Go to the underwriting queue</Button>
        </Link>
      </div>

      {/* Reviewer guided tour */}
      <div className="mt-10 rounded-md border border-rule bg-surface">
        <div className="border-b border-rule px-5 py-3">
          <p className="text-h2 text-ink">New here? Try it in three steps</p>
          <p className="text-caption text-ink-faint">
            No data to upload — six demo profiles are built in. The whole thing runs offline.
          </p>
        </div>
        <ol className="divide-y divide-rule">
          {TOUR.map((t) => (
            <li key={t.n} className="flex flex-col gap-2 p-5 sm:flex-row sm:items-start sm:gap-4">
              <span className="grid h-6 w-6 shrink-0 place-items-center rounded-sm bg-brand-tint font-mono text-mono-sm text-brand">
                {t.n}
              </span>
              <div className="flex-1">
                <p className="text-body-strong text-ink">{t.head}</p>
                <p className="mt-0.5 text-body text-ink-muted">{t.body}</p>
              </div>
              <Link
                href={t.href}
                className="mt-1 inline-flex shrink-0 items-center gap-1 self-start whitespace-nowrap rounded-sm border border-rule-strong px-3 py-1.5 text-body-strong text-brand transition-tokens hover:bg-brand-tint"
              >
                {t.cta} <ArrowRight size={13} />
              </Link>
            </li>
          ))}
        </ol>
      </div>

      <div className="mt-8 grid gap-px overflow-hidden rounded-md border border-rule bg-rule sm:grid-cols-3">
        {STEPS.map((s) => (
          <div key={s.title} className="bg-surface p-5">
            <s.icon size={18} strokeWidth={1.5} className="text-brand" aria-hidden />
            <p className="mt-2 text-h2 text-ink">{s.title}</p>
            <p className="mt-1 text-body text-ink-muted">{s.body}</p>
          </div>
        ))}
      </div>

      {/* Creators */}
      <div className="mt-10 rounded-md border border-rule bg-surface">
        <div className="border-b border-rule px-5 py-3">
          <p className="text-h2 text-ink">Built by</p>
          <p className="text-caption text-ink-faint">
            A two-person team, National University of Sciences &amp; Technology (NUST), Islamabad.
          </p>
        </div>
        <ul className="grid gap-px bg-rule sm:grid-cols-2">
          {CREATORS.map((c) => (
            <li key={c.name} className="flex items-center gap-4 bg-surface p-5">
              <span className="block h-14 w-14 shrink-0 overflow-hidden rounded-full border border-rule">
                <Image
                  src={c.photo}
                  alt={c.name}
                  width={56}
                  height={56}
                  className="h-full w-full object-cover"
                />
              </span>
              <div className="min-w-0">
                <p className="text-body-strong text-ink">{c.name}</p>
                <p className="text-caption text-ink-muted">{c.role}</p>
                <a
                  href={c.linkedin}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-0.5 inline-flex items-center gap-1 text-caption text-brand hover:underline"
                >
                  LinkedIn <ArrowRight size={11} />
                </a>
              </div>
            </li>
          ))}
        </ul>
      </div>

      <Disclaimer className="mt-8" />
    </div>
  );
}
