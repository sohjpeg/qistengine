import { cn } from "@/lib/utils";

/** A text badge, not a pill: coloured text on a tint, 3px radius. */
export function Badge({
  className,
  tone = "neutral",
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & {
  tone?: "neutral" | "brand" | "low" | "medium" | "high" | "very-high";
}) {
  const tones: Record<string, string> = {
    neutral: "bg-surface-sunk text-ink-muted",
    brand: "bg-brand-tint text-brand",
    low: "bg-band-low-tint text-band-low",
    medium: "bg-band-medium-tint text-band-medium",
    high: "bg-band-high-tint text-band-high",
    "very-high": "bg-band-very-high-tint text-band-very-high",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-sm px-2 py-px text-label uppercase",
        tones[tone],
        className,
      )}
      {...props}
    />
  );
}
