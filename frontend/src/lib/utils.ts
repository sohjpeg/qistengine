import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

// The design system replaces Tailwind's default type scale and colour palette
// with custom tokens. tailwind-merge must be told which custom `text-*` names are
// font-sizes and which are colours, or it treats e.g. `text-body` as a colour and
// silently drops `text-white` from `bg-brand text-white ... text-body`.
const FONT_SIZES = [
  "score-hero", "display", "h1", "h2", "body", "body-strong", "figure", "label",
  "caption", "mono-sm",
];
const COLORS = [
  "paper", "surface", "surface-sunk", "rule", "rule-strong", "ink", "ink-muted",
  "ink-faint", "brand", "brand-hover", "brand-tint", "band-low", "band-low-tint",
  "band-medium", "band-medium-tint", "band-high", "band-high-tint",
  "band-very-high", "band-very-high-tint", "ledger-credit", "ledger-debit",
  "ledger-rule", "focus",
];

const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": [{ text: FONT_SIZES }],
      "text-color": [{ text: COLORS }],
      "bg-color": [{ bg: COLORS }],
      "border-color": [{ border: COLORS }],
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
