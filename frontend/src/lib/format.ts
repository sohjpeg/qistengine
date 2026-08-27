/** PKR, dates, percentages — one formatter each, used everywhere. */

const NBSP = " ";

/** Rs 55,000 — "Rs", a non-breaking space, grouped digits. Never ₨, never $. */
export function pkr(value: number | null | undefined, opts?: { compact?: boolean }): string {
  if (value === null || value === undefined || Number.isNaN(value)) return `Rs${NBSP}—`;
  const n = Math.round(value);
  if (opts?.compact) {
    const abs = Math.abs(n);
    if (abs >= 10_000_000) return `Rs${NBSP}${(n / 10_000_000).toFixed(1)}${NBSP}crore`;
    if (abs >= 100_000) return `Rs${NBSP}${(n / 100_000).toFixed(1)}${NBSP}lakh`;
  }
  return `Rs${NBSP}${n.toLocaleString("en-PK")}`;
}

/** 14 Aug 2026 — day-first, never 08/14/26. */
export function fmtDate(input: string | Date | null | undefined): string {
  if (!input) return "—";
  const d = typeof input === "string" ? new Date(input) : input;
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

export function fmtDateTime(input: string | Date | null | undefined): string {
  if (!input) return "—";
  const d = typeof input === "string" ? new Date(input) : input;
  if (Number.isNaN(d.getTime())) return "—";
  return `${fmtDate(d)}, ${d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}`;
}

/** Month key "2026-08" -> "Aug 2026" */
export function fmtMonth(ym: string): string {
  const [y, m] = ym.split("-").map(Number);
  if (!y || !m) return ym;
  return new Date(y, m - 1, 1).toLocaleDateString("en-GB", { month: "short", year: "2-digit" });
}

/** Percentages to one decimal. */
export function pct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

/** Ratios to two decimals. */
export function ratio(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(2);
}

export function signedPts(n: number): string {
  return n > 0 ? `+${n}` : `${n}`;
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || "—";
}
