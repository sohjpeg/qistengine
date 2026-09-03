"use client";

/**
 * Recharts 2.12 triggers a React "defaultProps will be removed" warning from
 * inside its own XAxis / YAxis components. It is upstream, harmless, and fixed in
 * a later Recharts line we have not pinned to. Swallow *only* that exact message
 * so the console stays clean for real issues.
 */
if (typeof window !== "undefined") {
  const w = window as unknown as { __chartNoiseSuppressed?: boolean };
  if (!w.__chartNoiseSuppressed) {
    w.__chartNoiseSuppressed = true;
    const original = console.error;
    console.error = (...args: unknown[]) => {
      const first = typeof args[0] === "string" ? args[0] : "";
      if (
        first.includes("defaultProps") &&
        args.some((a) => a === "XAxis" || a === "YAxis")
      ) {
        return;
      }
      original(...(args as []));
    };
  }
}

export function SuppressChartNoise() {
  return null;
}
