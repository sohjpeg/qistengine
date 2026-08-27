import { cn } from "@/lib/utils";
import { signedPts } from "@/lib/format";
import type { ReasonCode } from "@/lib/types";

/** Used in the print view and the queue hover preview; the ledger replaces it on
 *  the detail page. Sorted by absolute impact. */
export function ReasonCodeList({
  codes,
  limit,
  showUrdu = false,
}: {
  codes: ReasonCode[];
  limit?: number;
  showUrdu?: boolean;
}) {
  const sorted = [...codes]
    .filter((c) => c.impact_points !== 0)
    .sort((a, b) => Math.abs(b.impact_points) - Math.abs(a.impact_points))
    .slice(0, limit ?? codes.length);

  return (
    <ul className="divide-y divide-rule">
      {sorted.map((c) => (
        <li key={c.feature} className="flex items-start gap-3 py-2">
          <span
            className={cn(
              "mt-px w-12 shrink-0 text-end font-mono text-mono-sm tabular-nums",
              c.direction === "positive" ? "text-ledger-credit" : "text-ledger-debit",
            )}
          >
            {signedPts(c.impact_points)}
          </span>
          <span className="text-body text-ink">
            {c.label_en.replace(/^[+-]?\d+\s*pts\s*—\s*/, "")}
            {showUrdu ? (
              <span className="urdu block text-caption text-ink-faint">
                {c.label_ur.replace(/^[+-]?\d+\s*[^\s—]*\s*—\s*/, "")}
              </span>
            ) : null}
          </span>
        </li>
      ))}
    </ul>
  );
}

/** Two-column "Strengths / Risk factors" split used on the detail page. */
export function ReasonCodeColumns({ codes }: { codes: ReasonCode[] }) {
  const strengths = codes.filter((c) => c.direction === "positive");
  const risks = codes.filter((c) => c.direction === "negative");
  return (
    <div className="grid gap-6 sm:grid-cols-2">
      <div>
        <p className="mb-2 text-label uppercase text-ink-muted">Strengths</p>
        {strengths.length ? <ReasonCodeList codes={strengths} showUrdu /> : <Empty />}
      </div>
      <div>
        <p className="mb-2 text-label uppercase text-ink-muted">Risk factors</p>
        {risks.length ? <ReasonCodeList codes={risks} showUrdu /> : <Empty />}
      </div>
    </div>
  );
}

function Empty() {
  return <p className="py-2 text-caption text-ink-faint">None surfaced at this threshold.</p>;
}
