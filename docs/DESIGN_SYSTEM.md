# Design system — the single source of truth

Every colour, size and radius in the codebase comes from a token defined in
`frontend/src/app/globals.css` and mapped in `frontend/tailwind.config.ts`. A raw
hex value or a Tailwind default class (`bg-blue-500`) inside a component is a bug.

## Thesis

The ancestor of this product is the **khata** — the hand-ruled ledger book a
Pakistani shopkeeper keeps under the counter: red column rules, ink entries, a
running balance down the right edge, everything totalling to something you can
check by hand. The second ancestor is the computerised utility bill: perforated,
monospaced, tabular, unglamorous.

QistEngine is **a document, not an app-shaped dashboard**: light, dense, ruled,
typeset, printable. An underwriter reads it on a 1366×768 monitor under
fluorescent light, then prints the credit memo for the file. **The interface is
light, not dark.**

## Colour tokens

Surfaces `--paper #FAFAF8` · `--surface #FFFFFF` · `--surface-sunk #F2F1EC` ·
`--rule #E3E1DA` · `--rule-strong #C9C6BC`
Ink `--ink #17191C` · `--ink-muted #565B63` · `--ink-faint #8B9098`
Brand `--brand #1B3A6B` · `--brand-hover #16305A` · `--brand-tint #EAEFF6`
Risk bands (print inks — each passes 4.5:1 as text on its own tint):
`--band-low #1E6E52` · `--band-medium #8A6A16` · `--band-high #9E5320` ·
`--band-very-high #9B2C2C`, each with a `-tint` background.
Ledger `--ledger-credit #1E6E52` · `--ledger-debit #9B2C2C` ·
`--ledger-rule #C4392F` (the red column rule, once per page).

**Colour is never the only carrier of meaning.** Every risk band also has a
distinct label and a distinct Lucide glyph (`ShieldCheck`, `AlertCircle`,
`AlertTriangle`, `XOctagon`), so bands survive greyscale and colour-vision
deficiency.

## Typography

Self-hosted via `next/font/local` from `public/fonts/` — no Google Fonts CDN.

| Role | Face | Where |
|------|------|-------|
| UI / body | IBM Plex Sans 400/500/600 | everything by default |
| Figures / ledger | IBM Plex Mono 400/500/600 | every number |
| Document | IBM Plex Serif 500/600 | credit-memo header, adverse-action notice, print |
| Urdu | Noto Nastaliq Urdu 400 | every `label_ur` string |

`.urdu` utility: `line-height: 2.1`, extra vertical padding, `direction: rtl` —
Nastaliq descends steeply and collides at English line-heights.

Type scale is fixed (`score-hero` 56, `display` 28, `h1` 22, `h2` 17, `body` 14,
`figure` 14 mono, `label` 12 uppercase, `caption` 12, `mono-sm` 12). No arbitrary
sizes. `font-variant-numeric: tabular-nums` on every figure.

## Spacing, radius, elevation

- Base unit 4px. Permitted: 4 8 12 16 20 24 32 40 48 64. Nothing else.
- Radius: `--r-sm 3px` (inputs, badges, buttons), `--r-md 6px` (cards), `--r-lg
  10px` (modals only). Nothing is a pill. Nothing is `rounded-2xl`.
- **No card gets a shadow, ever.** Separation is a 1px `--rule` hairline or a
  tone change to `--surface-sunk`. The only two shadows are `--shadow-pop`
  (popovers, toasts) and `--shadow-modal` (modals).
- Density: table rows 44px, header 36px, inputs 36px, buttons 34/38px, card
  padding 20px, section gap 24px.

## Motion

One orchestrated moment — the `ScoreLedger` writing itself on mount (opening
balance, then each line at 90 ms intervals, closing score counting up in
lockstep, < 1.1 s, `requestAnimationFrame`, collapses to final frame under
`prefers-reduced-motion`). Everything else: 150 ms colour/opacity transitions
only. **Never `hover:scale`.** No scroll reveals, no staggered fade-ins.

## Charts

Central theme in `src/lib/chartTheme.ts`. No vertical grid lines, no axis lines,
no boxed legend, no default tooltip. Horizontal grid only, in `--rule`. Custom
card tooltip with a hairline and mono figures. Series use `--brand` and its
tints; only risk-band data uses band colours. Area fills are a flat 10% of the
stroke — no gradients. Every chart has a caption stating what it shows and over
what period.

## Copy

Buttons name their outcome and the outcome keeps the name (`Approve loan` →
`Loan approved` → `Approved`; never `Submit`). Errors state what happened and
what to do, no apology. Empty states are instructions with a link. Sentence case
except the `label` role. No emoji anywhere.

Banned words: seamlessly, effortlessly, unlock, empower, revolutionise, leverage
(verb), "powered by AI", harness, "in seconds", any sentence starting "Simply".

## Accessibility floor

Focus ring `outline: 2px solid var(--focus); outline-offset: 2px` on every
interactive element. 4.5:1 body/figures, 3:1 large display. Queue table is
keyboard navigable (arrows move rows, Enter opens). Every icon-only button has
`aria-label`. Every chart has an adjacent `<table class="sr-only">`. The score
gauge is `role="img"` with a full `aria-label`.

## Print

`@media print` in `globals.css`: hide nav and controls (`.no-print`), switch the
memo header to Plex Serif (`.print-serif`), force white, expand collapsed panels,
add a fixed footer with application ID, model version, score and timestamp.
`Ctrl-P` on `/dashboard/[id]` produces a clean single-page A4 credit memo.

## Locale

`pkr()` → `Rs 55,000` (Rs, non-breaking space, grouped digits; `Rs 1.2 lakh` /
`Rs 3.5 crore` in dense contexts). `fmtDate()` → `14 Aug 2026` (day-first).
Percentages one decimal, ratios two. Logical properties throughout (`ps-`, `me-`,
`text-start`, `border-s`) so an RTL toggle is one attribute.

## Design review (Appendix B) — recorded in `DECISIONS.md`
