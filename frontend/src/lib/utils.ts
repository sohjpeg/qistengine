import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

// The project's font-size scale (tailwind.config.ts) uses named tokens like
// `text-body` / `text-h1` instead of t-shirt sizes. Without this, tailwind-merge
// can't tell them apart from text-color utilities (`text-white`, `text-ink`, ...)
// and silently drops whichever one comes second — see Button.tsx primary variant.
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": [
        {
          text: [
            "score-hero",
            "display",
            "h1",
            "h2",
            "body",
            "body-strong",
            "figure",
            "label",
            "caption",
            "mono-sm",
          ],
        },
      ],
    },
  },
});

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

import type { RiskBand } from "./types";

export const BAND_META: Record<
  RiskBand,
  { label: string; policy: string; text: string; tint: string; glyph: string }
> = {
  LOW: {
    label: "Low risk",
    policy: "Auto-approve up to limit",
    text: "text-band-low",
    tint: "bg-band-low-tint",
    glyph: "ShieldCheck",
  },
  MEDIUM: {
    label: "Medium risk",
    policy: "Manual review, reduced tenor",
    text: "text-band-medium",
    tint: "bg-band-medium-tint",
    glyph: "AlertCircle",
  },
  HIGH: {
    label: "High risk",
    policy: "Guarantor or collateral required",
    text: "text-band-high",
    tint: "bg-band-high-tint",
    glyph: "AlertTriangle",
  },
  VERY_HIGH: {
    label: "Very high risk",
    policy: "Decline, offer financial-literacy referral",
    text: "text-band-very-high",
    tint: "bg-band-very-high-tint",
    glyph: "XOctagon",
  },
};

export const BAND_HEX: Record<RiskBand, string> = {
  LOW: "#1e6e52",
  MEDIUM: "#8a6a16",
  HIGH: "#9e5320",
  VERY_HIGH: "#9b2c2c",
};

export function statusLabel(status: string): string {
  return (
    {
      PENDING: "Pending",
      SCORED: "Awaiting decision",
      APPROVED: "Approved",
      REJECTED: "Rejected",
      NEEDS_INFO: "Info requested",
    }[status] ?? status
  );
}
