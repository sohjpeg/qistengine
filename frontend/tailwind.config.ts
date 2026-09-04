import type { Config } from "tailwindcss";

/**
 * Every colour, radius, and shadow is a token defined in globals.css and mapped
 * here. No raw Tailwind palette classes anywhere in the app.
 */
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    colors: {
      transparent: "transparent",
      current: "currentColor",
      paper: "var(--paper)",
      surface: "var(--surface)",
      "surface-sunk": "var(--surface-sunk)",
      rule: "var(--rule)",
      "rule-strong": "var(--rule-strong)",
      ink: "var(--ink)",
      "ink-muted": "var(--ink-muted)",
      "ink-faint": "var(--ink-faint)",
      brand: "var(--brand)",
      "brand-hover": "var(--brand-hover)",
      "brand-tint": "var(--brand-tint)",
      "band-low": "var(--band-low)",
      "band-low-tint": "var(--band-low-tint)",
      "band-medium": "var(--band-medium)",
      "band-medium-tint": "var(--band-medium-tint)",
      "band-high": "var(--band-high)",
      "band-high-tint": "var(--band-high-tint)",
      "band-very-high": "var(--band-very-high)",
      "band-very-high-tint": "var(--band-very-high-tint)",
      "ledger-credit": "var(--ledger-credit)",
      "ledger-debit": "var(--ledger-debit)",
      "ledger-rule": "var(--ledger-rule)",
      focus: "var(--focus)",
      white: "#FFFFFF",
    },
    borderRadius: {
      none: "0",
      sm: "var(--r-sm)",
      md: "var(--r-md)",
      lg: "var(--r-lg)",
    },
    boxShadow: {
      none: "none",
      pop: "var(--shadow-pop)",
      modal: "var(--shadow-modal)",
    },
    // Spacing keeps Tailwind's standard 4px-based scale (a documented scale, not
    // arbitrary values). Layout rhythm sticks to 4 8 12 16 20 24 32 40 48 64;
    // the fractional steps are used only for sub-4px icon/label gaps. Bracketed
    // arbitrary spacing (p-[13px]) is banned; component heights the spec fixes in
    // px (34/36/38/44/52) are the one allowed use of bracket values.
    fontFamily: {
      sans: ["var(--font-plex-sans)", "system-ui", "sans-serif"],
      mono: ["var(--font-plex-mono)", "ui-monospace", "monospace"],
      serif: ["var(--font-plex-serif)", "Georgia", "serif"],
      urdu: ["var(--font-nastaliq)", "var(--font-plex-sans)", "serif"],
    },
    fontSize: {
      "score-hero": ["56px", { lineHeight: "56px", letterSpacing: "-0.03em", fontWeight: "600" }],
      display: ["28px", { lineHeight: "34px", letterSpacing: "-0.02em", fontWeight: "600" }],
      h1: ["22px", { lineHeight: "28px", letterSpacing: "-0.01em", fontWeight: "600" }],
      h2: ["17px", { lineHeight: "24px", fontWeight: "600" }],
      body: ["14px", { lineHeight: "21px" }],
      "body-strong": ["14px", { lineHeight: "21px", fontWeight: "500" }],
      figure: ["14px", { lineHeight: "20px", fontWeight: "500" }],
      label: ["12px", { lineHeight: "16px", letterSpacing: "0.04em", fontWeight: "500" }],
      caption: ["12px", { lineHeight: "17px" }],
      "mono-sm": ["12px", { lineHeight: "16px" }],
    },
    extend: {
      maxWidth: { content: "1440px" },
      transitionTimingFunction: { snap: "cubic-bezier(0.2, 0, 0.13, 1)" },
    },
  },
  plugins: [],
};

export default config;
