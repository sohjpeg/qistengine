"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Check } from "lucide-react";
import { FileDropzone } from "@/components/FileDropzone";
import { MockProfileLoader } from "@/components/MockProfileLoader";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { Disclaimer } from "@/components/ui/Disclaimer";
import { cn } from "@/lib/utils";
import { pkr } from "@/lib/format";
import { api, ApiError } from "@/lib/api";
import { DEMO_MODE, MOCK_PROFILES as CACHED_PROFILES } from "@/lib/mockProfiles";
import type { ExtractedField, MockProfile } from "@/lib/types";

const STEPS = ["Identity & business", "Documents", "Loan request & review"];
const ARCHETYPES = [
  ["kiryana_merchant", "Kiryana / grocery merchant"],
  ["daily_wage_worker", "Daily-wage worker"],
  ["home_based_producer", "Home-based producer"],
  ["ride_hailing_driver", "Ride-hailing driver"],
];

function maskCnic(v: string) {
  const d = v.replace(/\D/g, "").slice(0, 13);
  const parts = [d.slice(0, 5), d.slice(5, 12), d.slice(12, 13)].filter(Boolean);
  return parts.join("-");
}

interface FormState {
  full_name: string;
  cnic: string;
  phone: string;
  city: string;
  archetype: string;
  business_type: string;
  dependents_count: number;
  has_fixed_premises: boolean;
  requested_amount_pkr: number;
  purpose: string;
  features: Record<string, number>;
  billFields: ExtractedField[];
  billMethod: string;
}

const EMPTY: FormState = {
  full_name: "",
  cnic: "",
  phone: "",
  city: "Karachi",
  archetype: "kiryana_merchant",
  business_type: "",
  dependents_count: 3,
  has_fixed_premises: false,
  requested_amount_pkr: 60000,
  purpose: "",
  features: {},
  billFields: [],
  billMethod: "",
};

export default function ApplyPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [form, setForm] = useState<FormState>(EMPTY);
  const [profiles, setProfiles] = useState<MockProfile[]>([]);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api
      .mockProfiles()
      .then(setProfiles)
      .catch(() => setProfiles(CACHED_PROFILES));
  }, []);

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  function loadProfile(p: MockProfile) {
    setForm({
      full_name: p.applicant.full_name,
      cnic: p.applicant.cnic,
      phone: p.applicant.phone,
      city: p.city,
      archetype: p.archetype,
      business_type: p.business_type,
      dependents_count: p.applicant.dependents_count,
      has_fixed_premises: p.applicant.has_fixed_premises,
      requested_amount_pkr: p.requested_amount_pkr,
      purpose: p.purpose,
      features: { ...p.features },
      billFields: Object.entries(p.bill_fields).map(([name, value]) => ({
        name,
        value: value as string | number,
        confidence: 0.9,
      })),
      billMethod: "supplied",
    });
    setStep(2);
    toast.success(`Loaded ${p.display_name}`);
  }

  async function handleBill(file: File) {
    const res = await api.parseBill(file);
    set("billFields", res.fields);
    set("billMethod", res.extraction_method);
    setForm((f) => ({ ...f, features: { ...f.features, ...res.derived_features } }));
  }

  async function handleTxns(file: File) {
    const res = await api.parseTransactions(file);
    setForm((f) => ({ ...f, features: { ...f.features, ...res.derived_features } }));
  }

  async function submit() {
    setSubmitting(true);
    try {
      const billFieldsObj: Record<string, unknown> = { _extraction_method: form.billMethod };
      form.billFields.forEach((fld) => {
        if (fld.value !== null && fld.value !== "") billFieldsObj[fld.name] = fld.value;
      });
      const detail = await api.createApplication({
        applicant: {
          full_name: form.full_name,
          cnic: form.cnic,
          phone: form.phone,
          city: form.city,
          archetype: form.archetype,
          business_type: form.business_type,
          dependents_count: form.dependents_count,
          has_fixed_premises: form.has_fixed_premises,
        },
        requested_amount_pkr: form.requested_amount_pkr,
        purpose: form.purpose,
        features: form.features,
        bill_fields: billFieldsObj,
      });
      toast.success("Application submitted and scored");
      router.push(`/dashboard/${detail.id}`);
    } catch (e) {
      const msg = e instanceof ApiError ? e.detail : "Could not submit the application.";
      toast.error(msg);
      setSubmitting(false);
    }
  }

  const canNext = useMemo(() => {
    if (step === 0) return form.full_name && form.cnic.replace(/\D/g, "").length >= 13 && form.business_type;
    if (step === 2) return form.purpose && form.requested_amount_pkr > 0;
    return true;
  }, [step, form]);

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-h1 text-ink">Applicant portal</h1>
      <p className="mt-1 text-body text-ink-muted">
        Three steps. Your CNIC is masked as you type and never leaves the browser unmasked.
      </p>

      <div className="mt-5">
        <MockProfileLoader profiles={profiles} onLoad={loadProfile} />
      </div>

      {/* progress rail */}
      <ol className="mt-6 flex items-center gap-2">
        {STEPS.map((s, i) => (
          <li key={s} className="flex flex-1 items-center gap-2">
            <button
              onClick={() => i < step && setStep(i)}
              aria-label={`Step ${i + 1}: ${s}${i < step ? " (completed, click to go back)" : i === step ? " (current)" : ""}`}
              aria-current={i === step ? "step" : undefined}
              className={cn(
                "grid h-6 w-6 shrink-0 place-items-center rounded-sm text-mono-sm",
                i < step
                  ? "bg-brand text-white"
                  : i === step
                    ? "border border-brand text-brand"
                    : "border border-rule text-ink-faint",
              )}
            >
              {i < step ? <Check size={13} /> : i + 1}
            </button>
            <span className={cn("text-caption", i === step ? "text-ink" : "text-ink-faint")}>{s}</span>
            {i < STEPS.length - 1 && <span className="h-px flex-1 bg-rule" />}
          </li>
        ))}
      </ol>

      <Card className="mt-4">
        <CardBody>
          {step === 0 && (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Full name">
                <input className="qi" value={form.full_name} onChange={(e) => set("full_name", e.target.value)} />
              </Field>
              <Field label="CNIC">
                <input
                  className="qi font-mono"
                  value={form.cnic}
                  onChange={(e) => set("cnic", maskCnic(e.target.value))}
                  placeholder="xxxxx-xxxxxxx-x"
                  inputMode="numeric"
                />
              </Field>
              <Field label="Phone">
                <input className="qi font-mono" value={form.phone} onChange={(e) => set("phone", e.target.value)} placeholder="03xx-xxxxxxx" />
              </Field>
              <Field label="City">
                <select className="qi" value={form.city} onChange={(e) => set("city", e.target.value)}>
                  {["Karachi", "Lahore", "Faisalabad", "Rawalpindi", "Multan", "Peshawar", "Quetta", "Hyderabad", "Sialkot", "Gujranwala"].map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </Field>
              <Field label="Livelihood">
                <select className="qi" value={form.archetype} onChange={(e) => set("archetype", e.target.value)}>
                  {ARCHETYPES.map(([v, l]) => (
                    <option key={v} value={v}>
                      {l}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Business type">
                <input className="qi" value={form.business_type} onChange={(e) => set("business_type", e.target.value)} />
              </Field>
              <Field label="Dependents">
                <input
                  type="number"
                  min={0}
                  className="qi font-mono"
                  value={form.dependents_count}
                  onFocus={(e) => e.target.select()}
                  onChange={(e) => set("dependents_count", Math.max(0, Number(e.target.value) || 0))}
                />
              </Field>
              <label className="flex items-center gap-2 pt-6 text-body text-ink">
                <input
                  type="checkbox"
                  checked={form.has_fixed_premises}
                  onChange={(e) => set("has_fixed_premises", e.target.checked)}
                />
                Operates from fixed business premises
              </label>
            </div>
          )}

          {step === 1 && (
            <div className="grid gap-5 sm:grid-cols-2">
              <div>
                <p className="mb-2 text-label uppercase text-ink-muted">Utility bill</p>
                <FileDropzone
                  label="Utility bill"
                  sampleName="karachi_kiryana_kelectric_bill.pdf"
                  onFile={handleBill}
                  parsedSummary={
                    form.billFields.length
                      ? { count: form.billFields.filter((f) => f.value != null).length, method: form.billMethod }
                      : null
                  }
                />
              </div>
              <div>
                <p className="mb-2 text-label uppercase text-ink-muted">Transaction log</p>
                <FileDropzone
                  label="Transaction log"
                  sampleName="karachi_kiryana_easypaisa_ledger.csv"
                  onFile={handleTxns}
                  parsedSummary={
                    Object.keys(form.features).length
                      ? { count: Object.keys(form.features).length, method: "parsed" }
                      : null
                  }
                />
              </div>

              {form.billFields.length > 0 && (
                <div className="sm:col-span-2">
                  <p className="mb-2 text-label uppercase text-ink-muted">
                    Extracted fields — correct anything the parser got wrong
                  </p>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {form.billFields.map((fld, i) => (
                      <label key={fld.name} className="text-caption text-ink-muted">
                        <span className="flex items-center gap-1.5">
                          <span
                            className={cn(
                              "inline-block h-1.5 w-1.5 rounded-full",
                              fld.confidence === 0
                                ? "bg-ink-faint"
                                : fld.confidence >= 0.8
                                  ? "bg-band-low"
                                  : "bg-band-medium",
                            )}
                          />
                          {fld.name}
                        </span>
                        <input
                          className="qi mt-1 font-mono"
                          value={fld.value ?? ""}
                          onChange={(e) => {
                            const next = [...form.billFields];
                            next[i] = { ...fld, value: e.target.value };
                            set("billFields", next);
                          }}
                        />
                      </label>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {step === 2 && (
            <div className="grid gap-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Requested amount (Rs)">
                  <input
                    type="number"
                    min={0}
                    className="qi font-mono"
                    value={form.requested_amount_pkr}
                    onFocus={(e) => e.target.select()}
                    onChange={(e) => set("requested_amount_pkr", Math.max(0, Number(e.target.value) || 0))}
                  />
                </Field>
                <Field label="Purpose">
                  <input className="qi" value={form.purpose} onChange={(e) => set("purpose", e.target.value)} />
                </Field>
              </div>
              <div className="rounded-sm bg-surface-sunk p-4">
                <p className="text-label uppercase text-ink-muted">Review</p>
                <dl className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 font-mono text-mono-sm">
                  <Row k="Applicant" v={form.full_name || "—"} />
                  <Row k="City" v={form.city} />
                  <Row k="Livelihood" v={form.archetype.replace(/_/g, " ")} />
                  <Row k="Business" v={form.business_type || "—"} />
                  <Row k="Requested" v={pkr(form.requested_amount_pkr)} />
                  <Row k="Signals captured" v={`${Object.keys(form.features).length} features`} />
                </dl>
                {Object.keys(form.features).length < 8 && (
                  <p className="mt-2 text-caption text-band-medium">
                    Thin data — the engine will impute the rest at population medians and lower the
                    confidence. That is expected for a first-time applicant.
                  </p>
                )}
              </div>
            </div>
          )}

          <div className="mt-6 flex items-center justify-between">
            <Button
              variant="ghost"
              size="sm"
              disabled={step === 0}
              onClick={() => setStep((s) => Math.max(0, s - 1))}
            >
              Back
            </Button>
            {step < 2 ? (
              <Button size="sm" disabled={!canNext} onClick={() => setStep((s) => s + 1)}>
                Continue
              </Button>
            ) : (
              <Button size="sm" disabled={!canNext || submitting} onClick={submit}>
                {submitting ? "Scoring…" : "Submit application"}
              </Button>
            )}
          </div>
        </CardBody>
      </Card>

      <Disclaimer className="mt-5" />

      <style jsx global>{`
        .qi {
          height: 36px;
          width: 100%;
          border: 1px solid var(--rule-strong);
          border-radius: var(--r-sm);
          background: var(--surface);
          padding: 0 8px;
          font-size: 14px;
          color: var(--ink);
        }
      `}</style>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="text-caption text-ink-muted">
      {label}
      <span className="mt-1 block">{children}</span>
    </label>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between border-b border-rule py-1">
      <dt className="text-ink-muted">{k}</dt>
      <dd className="text-ink">{v}</dd>
    </div>
  );
}
