"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { api, ApiError } from "@/lib/api";
import { pkr } from "@/lib/format";
import type { ApplicationDetail, DecisionType, ScoreResponse } from "@/lib/types";

const ACTIONS: { key: DecisionType; label: string; variant: "primary" | "secondary" | "ghost" | "danger" }[] = [
  { key: "APPROVE", label: "Approve loan", variant: "primary" },
  { key: "APPROVE_MODIFIED", label: "Approve with modification", variant: "secondary" },
  { key: "REQUEST_INFO", label: "Request info", variant: "ghost" },
  { key: "REJECT", label: "Reject", variant: "danger" },
];

export function DecisionPanel({
  application,
  score,
  onDecided,
}: {
  application: ApplicationDetail;
  score: ScoreResponse;
  onDecided: (next: ApplicationDetail) => void;
}) {
  const limit = score.qist_limit;
  const [choice, setChoice] = useState<DecisionType | null>(null);
  const [amount, setAmount] = useState<number>(limit.eligible ? limit.principal_pkr : 0);
  const [installment, setInstallment] = useState<number>(limit.eligible ? limit.safe_installment_pkr : 0);
  const [note, setNote] = useState("");
  const [justification, setJustification] = useState("");
  const [busy, setBusy] = useState(false);

  const existing = application.decision;
  const approving = choice === "APPROVE" || choice === "APPROVE_MODIFIED";
  const needsJustification =
    approving && (score.risk_band === "VERY_HIGH" || installment > limit.safe_installment_pkr);

  async function submit() {
    if (!choice) return;
    if (needsJustification && !justification.trim()) {
      toast.error("A written justification is required for this override.");
      return;
    }
    setBusy(true);
    // optimistic
    const optimistic: ApplicationDetail = {
      ...application,
      status:
        choice === "REJECT" ? "REJECTED" : choice === "REQUEST_INFO" ? "NEEDS_INFO" : "APPROVED",
    };
    onDecided(optimistic);
    try {
      const next = await api.recordDecision(application.id, {
        decision: choice,
        approved_amount_pkr: approving ? amount : null,
        approved_installment_pkr: approving ? installment : null,
        tenor_months: limit.tenor_months,
        officer_note: note,
        justification: needsJustification ? justification : null,
      });
      onDecided(next);
      const past = {
        APPROVE: "Loan approved",
        APPROVE_MODIFIED: "Loan approved with modification",
        REQUEST_INFO: "Information requested",
        REJECT: "Application rejected",
      }[choice];
      toast.success(past + (next.decision?.override_flag ? " · override recorded" : ""));
    } catch (e) {
      onDecided(application); // roll back
      const msg = e instanceof ApiError ? e.detail : "Could not record the decision.";
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  }

  if (existing) {
    return (
      <div className="rounded-md border border-rule bg-surface p-5">
        <p className="text-label uppercase text-ink-muted">Decision on file</p>
        <p className="mt-2 text-body-strong text-ink">
          {existing.decision.replace("_", " ")}
          {existing.override_flag ? (
            <span className="ms-2 rounded-sm bg-band-very-high-tint px-1.5 py-px text-label uppercase text-band-very-high">
              override
            </span>
          ) : null}
        </p>
        {existing.approved_amount_pkr ? (
          <p className="mt-1 font-mono text-figure text-ink-muted">
            {pkr(existing.approved_amount_pkr)} principal · {pkr(existing.approved_installment_pkr)}/mo ·{" "}
            {existing.tenor_months} months
          </p>
        ) : null}
        {existing.officer_note ? (
          <p className="mt-2 whitespace-pre-wrap text-body text-ink-muted">{existing.officer_note}</p>
        ) : null}
      </div>
    );
  }

  return (
    <div className="rounded-md border border-rule bg-surface p-5">
      <p className="text-label uppercase text-ink-muted">Underwriter decision</p>
      <div className="mt-3 grid grid-cols-2 gap-2">
        {ACTIONS.map((a) => (
          <Button
            key={a.key}
            variant={choice === a.key ? "primary" : "secondary"}
            size="sm"
            onClick={() => setChoice(a.key)}
          >
            {a.label}
          </Button>
        ))}
      </div>

      {approving && (
        <div className="mt-4 grid gap-3">
          <label className="text-caption text-ink-muted">
            Approved principal (Rs)
            <input
              type="number"
              min={0}
              value={amount === 0 ? "" : amount}
              placeholder="0"
              onFocus={(e) => e.target.select()}
              onChange={(e) => setAmount(Math.max(0, Number(e.target.value) || 0))}
              className="mt-1 h-9 w-full rounded-sm border border-rule-strong bg-surface px-2 font-mono text-body tabular-nums"
            />
          </label>
          <label className="text-caption text-ink-muted">
            Approved installment (Rs / month)
            <input
              type="number"
              min={0}
              value={installment === 0 ? "" : installment}
              placeholder="0"
              onFocus={(e) => e.target.select()}
              onChange={(e) => setInstallment(Math.max(0, Number(e.target.value) || 0))}
              className="mt-1 h-9 w-full rounded-sm border border-rule-strong bg-surface px-2 font-mono text-body tabular-nums"
            />
            {installment > limit.safe_installment_pkr ? (
              <span className="mt-1 block text-caption text-band-high">
                Above the safe installment of {pkr(limit.safe_installment_pkr)} — this will be flagged as an override.
              </span>
            ) : null}
          </label>
        </div>
      )}

      {choice && (
        <label className="mt-3 block text-caption text-ink-muted">
          Officer note
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={2}
            className="mt-1 w-full rounded-sm border border-rule-strong bg-surface px-2 py-1.5 text-body"
          />
        </label>
      )}

      {needsJustification && (
        <label className="mt-3 block text-caption text-band-very-high">
          Written justification (required for this override)
          <textarea
            value={justification}
            onChange={(e) => setJustification(e.target.value)}
            rows={2}
            className="mt-1 w-full rounded-sm border border-band-very-high/40 bg-band-very-high-tint px-2 py-1.5 text-body text-ink"
          />
        </label>
      )}

      <Button className="mt-4 w-full" disabled={!choice || busy} onClick={submit}>
        {busy ? "Recording…" : "Record decision"}
      </Button>
    </div>
  );
}
