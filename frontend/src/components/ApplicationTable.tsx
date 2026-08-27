"use client";

import { ChevronDown, ChevronUp } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { RiskBadge } from "@/components/RiskBadge";
import { ScoreGauge } from "@/components/ScoreGauge";
import { cn, statusLabel } from "@/lib/utils";
import { fmtDate, pkr } from "@/lib/format";
import type { ApplicationSummary, RiskBand } from "@/lib/types";

type SortKey = "score" | "date";

export function ApplicationTable({ rows }: { rows: ApplicationSummary[] }) {
  const router = useRouter();
  const [sort, setSort] = useState<SortKey>("date");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [active, setActive] = useState(0);
  const bodyRef = useRef<HTMLTableSectionElement>(null);

  const sorted = [...rows].sort((a, b) => {
    const av = sort === "score" ? a.score ?? -1 : new Date(a.submitted_at).getTime();
    const bv = sort === "score" ? b.score ?? -1 : new Date(b.submitted_at).getTime();
    return order === "desc" ? bv - av : av - bv;
  });

  function toggleSort(key: SortKey) {
    if (sort === key) setOrder(order === "desc" ? "asc" : "desc");
    else {
      setSort(key);
      setOrder("desc");
    }
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(sorted.length - 1, i + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(0, i - 1));
    } else if (e.key === "Enter" && sorted[active]) {
      router.push(`/dashboard/${sorted[active].id}`);
    }
  }

  if (!rows.length) {
    return (
      <div className="rounded-md border border-rule bg-surface p-10 text-center">
        <p className="text-body-strong text-ink">No applications match these filters.</p>
        <p className="mt-1 text-body text-ink-muted">
          Clear the filters, or load a demo profile from the{" "}
          <a href="/apply" className="text-brand underline">
            applicant portal
          </a>{" "}
          to see a score.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-md border border-rule">
      <table
        className="w-full min-w-[820px] border-collapse text-body"
        onKeyDown={onKeyDown}
        tabIndex={0}
        aria-label="Applications queue. Use arrow keys to move between rows, Enter to open."
      >
        <thead>
          <tr className="sticky top-0 bg-surface-sunk text-label uppercase text-ink-muted">
            <Th>Applicant</Th>
            <Th>City</Th>
            <Th sortable active={sort === "score"} order={order} onClick={() => toggleSort("score")} className="text-end">
              Score
            </Th>
            <Th>Band</Th>
            <Th className="text-end">Requested</Th>
            <Th className="text-end">Safe limit</Th>
            <Th>Status</Th>
            <Th sortable active={sort === "date"} order={order} onClick={() => toggleSort("date")}>
              Submitted
            </Th>
          </tr>
        </thead>
        <tbody ref={bodyRef} className="divide-y divide-rule bg-surface">
          {sorted.map((r, i) => (
            <tr
              key={r.id}
              onClick={() => router.push(`/dashboard/${r.id}`)}
              onMouseEnter={() => setActive(i)}
              className={cn(
                "h-[44px] cursor-pointer transition-tokens",
                i === active ? "bg-brand-tint" : "hover:bg-brand-tint",
                i === active && "border-s-2 border-s-brand",
              )}
            >
              <td className="px-3">
                <span className="flex items-center gap-2">
                  <span className="grid h-6 w-6 place-items-center rounded-sm bg-surface-sunk text-mono-sm text-ink-muted">
                    {r.applicant_name.split(" ").map((p) => p[0]).slice(0, 2).join("")}
                  </span>
                  <span className="text-body-strong text-ink">{r.applicant_name}</span>
                  {r.override_flag ? <span className="text-caption text-band-very-high">override</span> : null}
                </span>
              </td>
              <td className="px-3 text-ink-muted">{r.city}</td>
              <td className="px-3 text-end">
                <span className="flex items-center justify-end gap-2">
                  {r.score ? <ScoreGauge score={r.score} band={(r.risk_band ?? "VERY_HIGH") as RiskBand} size="sm" /> : null}
                  <span className="font-mono tabular-nums text-ink">{r.score ?? "—"}</span>
                </span>
              </td>
              <td className="px-3">{r.risk_band ? <RiskBadge band={r.risk_band} /> : <span className="text-ink-faint">—</span>}</td>
              <td className="px-3 text-end font-mono tabular-nums text-ink">{pkr(r.requested_amount_pkr)}</td>
              <td className="px-3 text-end font-mono tabular-nums text-ink-muted">
                {r.safe_installment_pkr ? pkr(r.safe_installment_pkr) : "—"}
              </td>
              <td className="px-3 text-ink-muted">{statusLabel(r.status)}</td>
              <td className="px-3 font-mono text-mono-sm text-ink-faint">{fmtDate(r.submitted_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Th({
  children,
  className,
  sortable,
  active,
  order,
  onClick,
}: {
  children: React.ReactNode;
  className?: string;
  sortable?: boolean;
  active?: boolean;
  order?: "asc" | "desc";
  onClick?: () => void;
}) {
  return (
    <th className={cn("h-9 px-3 text-start font-medium", className)}>
      {sortable ? (
        <button onClick={onClick} className="inline-flex items-center gap-1 hover:text-ink">
          {children}
          {active ? (
            order === "desc" ? (
              <ChevronDown size={12} />
            ) : (
              <ChevronUp size={12} />
            )
          ) : null}
        </button>
      ) : (
        children
      )}
    </th>
  );
}
