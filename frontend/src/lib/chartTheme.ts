/** Central Recharts styling. Every chart imports from here; no per-chart styling. */

export const CHART = {
  brand: "#1b3a6b",
  brandFillOpacity: 0.1,
  rule: "#e3e1da",
  inkFaint: "#8b9098",
  inkMuted: "#565b63",
  axisTick: { fill: "#8b9098", fontFamily: "var(--font-plex-mono), monospace", fontSize: 12 },
  grid: { stroke: "#e3e1da", strokeDasharray: "0" },
};

export const brandTints = ["#1b3a6b", "#3f5c85", "#6a80a2", "#9aa9bf", "#c3cddb"];

/** Shared tooltip renderer — a card with a hairline, mono figures, no default box. */
export function tooltipStyle() {
  return {
    background: "var(--surface)",
    border: "1px solid var(--rule)",
    borderRadius: "var(--r-md)",
    boxShadow: "var(--shadow-pop)",
    padding: "8px 12px",
    fontFamily: "var(--font-plex-mono), monospace",
    fontSize: "12px",
    color: "var(--ink)",
  } as const;
}
