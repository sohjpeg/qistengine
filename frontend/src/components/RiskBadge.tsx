import { AlertCircle, AlertTriangle, ShieldCheck, XOctagon } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { BAND_META } from "@/lib/utils";
import type { RiskBand } from "@/lib/types";

const GLYPH = {
  ShieldCheck,
  AlertCircle,
  AlertTriangle,
  XOctagon,
} as const;

const TONE: Record<RiskBand, "low" | "medium" | "high" | "very-high"> = {
  LOW: "low",
  MEDIUM: "medium",
  HIGH: "high",
  VERY_HIGH: "very-high",
};

/** Readable in greyscale: distinct label + distinct glyph per band. */
export function RiskBadge({ band }: { band: RiskBand }) {
  const meta = BAND_META[band];
  const Glyph = GLYPH[meta.glyph as keyof typeof GLYPH];
  return (
    <Badge tone={TONE[band]}>
      <Glyph size={12} strokeWidth={1.5} aria-hidden />
      {meta.label}
    </Badge>
  );
}
