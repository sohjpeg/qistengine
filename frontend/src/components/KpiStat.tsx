import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import { cn } from "@/lib/utils";

/** Three lines, no card, no border, no icon. Separated from neighbours by a hairline. */
export function KpiStat({
  label,
  value,
  delta,
}: {
  label: string;
  value: string;
  delta?: { text: string; direction: "up" | "down" | "flat"; tone?: "low" | "medium" | "high" | "very-high" };
}) {
  const toneClass = {
    low: "text-band-low",
    medium: "text-band-medium",
    high: "text-band-high",
    "very-high": "text-band-very-high",
  }[delta?.tone ?? "low"];
  return (
    <div className="flex flex-col gap-1 px-5 first:ps-0">
      <span className="text-label uppercase text-ink-muted">{label}</span>
      <span className="font-mono text-display tabular-nums text-ink">{value}</span>
      {delta ? (
        <span className={cn("flex items-center gap-1 text-caption", toneClass)}>
          {delta.direction === "up" ? (
            <ArrowUpRight size={12} strokeWidth={1.5} />
          ) : delta.direction === "down" ? (
            <ArrowDownRight size={12} strokeWidth={1.5} />
          ) : null}
          {delta.text}
        </span>
      ) : (
        <span className="text-caption text-ink-faint">&nbsp;</span>
      )}
    </div>
  );
}

export function KpiRow({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap divide-x divide-rule rounded-md border border-rule bg-surface px-5 py-4">
      {children}
    </div>
  );
}
