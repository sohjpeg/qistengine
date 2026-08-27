import { Info } from "lucide-react";
import { cn } from "@/lib/utils";
import { DISCLAIMER } from "@/lib/types";

/** Shown on every surface that displays a decision. */
export function Disclaimer({ className }: { className?: string }) {
  return (
    <p
      className={cn(
        "flex items-start gap-2 rounded-sm bg-surface-sunk px-3 py-2 text-caption text-ink-muted",
        className,
      )}
    >
      <Info size={13} className="mt-px shrink-0" strokeWidth={1.5} aria-hidden />
      <span>{DISCLAIMER}</span>
    </p>
  );
}
