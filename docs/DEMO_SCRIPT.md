# Demo script — five minutes

> Demonstration model on synthetic data. Not a regulated credit decision.
> Start with `bash run-dev.sh`. App at http://localhost:3000, API docs at
> http://localhost:8000/docs.

---

## 0:00–0:30 — The problem

> "This is a shopkeeper in Karachi. Twelve years behind the counter, a mobile
> wallet, an electricity meter in his name — and no credit file, because he was
> never allowed to build one. A bank asks for a loan history he could never have.
> QistEngine scores what he *does* generate: utility payments and wallet
> cashflow."

Open `/` — the three-card mechanism: **Ingest → Score → Decide.**

## 0:30–1:30 — Applicant portal

Go to `/apply`.

- Click the **Bilal — Karachi kiryana, high volume, volatile** quick-demo button.
  It fills all three steps and jumps to review. (Mention: "one click here; in a
  real flow the applicant uploads two files.")
- Go *back* to step 2 to show the dropzones. Drag
  `backend/data/samples/karachi_kiryana_kelectric_bill.pdf` onto the utility-bill
  dropzone. Fields populate as editable chips, each with a confidence dot —
  green for a clean PDF read.
- Note the amber **"simulated extraction"** chip you get for a PNG when the
  laptop has no Tesseract: *"it degrades honestly instead of crashing."*
- Submit.

## 1:30–2:30 — The score

Lands on `/dashboard/[id]`.

- The **score gauge** counts up to its value; the risk badge names the band.
- The **Qist limit card**: headline monthly installment, then the haircut
  waterfall — *"raw disposable income, then the DSR cap, the volatility haircut,
  the data-depth factor, the consistency bonus — every step labelled with what
  it removed."*
- Toggle the tenor selector (3 / 6 / 9 / 12) — principal recomputes with no
  network call.

## 2:30–3:30 — Explainability (the line that lands)

Scroll to the **Score ledger** — the khata page.

> "This isn't a generic list of reason pills. It's the score derivation as a
> shopkeeper's ledger: opening balance, each factor as a credit or a debit, a
> double-ruled total. And the total is *exact* — the score is affine in
> log-odds, SHAP values are additive in log-odds, so the column genuinely sums
> to the score. Add it up."

Point at the adverse-action notice: *"regulators require this in real lending —
the top three negative drivers as short codes."*

## 3:30–4:15 — Underwriter view

Back to `/dashboard`. The six demo profiles sit at the top of the queue, each at
a stable URL: `/dashboard/<slug>` — `nasreen-multan-homefood`,
`bilal-karachi-kiryana`, `farhan-rawalpindi-ridehailing`,
`imran-faisalabad-dailywage`, `ayesha-lahore-tailoring`,
`zubair-peshawar-autoparts`. Bookmark whichever you plan to open live.

- KPI strip: applications today, approval rate, mean score, portfolio expected
  loss, **override rate** (a governance metric).
- Filter by band = VERY_HIGH, or open **Imran** directly. In the decision panel
  choose **Approve loan** → because he is VERY_HIGH a red **written justification**
  box appears and blocks the decision until filled. Enter a reason, record it.
  Toast confirms **"Loan approved · override recorded"** and the panel shows the
  **OVERRIDE** badge.

## 4:15–5:00 — Analytics and the model card

Go to `/analytics`.

- Score distribution histogram coloured by band; approval rate by band;
  city breakdown; override-rate trend.
- The **model card**, pulled live from `/api/v1/model/info`: ROC-AUC 0.82,
  KS 0.49, Gini 0.64, Brier 0.10, base default rate 14.5%, and the fairness-audit
  headline.

> "The audit flags disparate impact by livelihood — daily-wage workers see far
> lower approval, driven by genuine cashflow risk, not a protected attribute. We
> document it and propose livelihood-specific limits. That honesty is the point."

---

## Fallback plan

- **Backend dies mid-demo.** With `NEXT_PUBLIC_DEMO_MODE=true` (the default),
  every page shows a recovery banner and serves cached score responses from
  `frontend/src/lib/_mock_data.json` for the six demo profiles. The queue and
  detail pages still render. Restart with `uvicorn app.main:app --reload` from
  `backend/`.
- **A route errors.** Every data surface has an explicit loading, empty and
  error state. The error state tells you the exact command to run.
- **Asked about real-data access.** Pakistan's **Raast** instant-payment rail and
  the SBP's open-banking direction; wallet-partnership APIs (JazzCash, EasyPaisa)
  for consented transaction pulls; DISCO bill-payment histories via 1LINK.

---

## Anticipated questions

**Is synthetic data valid?** It validates the *pipeline*, not the world. The
generator encodes credit intuition (utility discipline and cash buffer as the
strongest protective factors; volatility and expense burden as the strongest
risk factors), targets the microfinance sector's stressed 14% default band, and
adds measurement noise so AUC lands at a realistic 0.82 rather than a suspicious
0.97. Real deployment needs a pilot book and reject-inference.

**Three months of history instead of twelve?** `utility_months_observed` is a
feature and it feeds `depth_confidence` in the Qist limit, so a thin file gets a
smaller offer and a lower confidence score — not a decline. The partial-data path
imputes the missing block at population medians and returns a `data_gaps` array.
See the **Zubair** demo profile.

**Gaming resistance?** Circular P2P transfers to fake activity are exactly what
the non-monotonic `p2p_velocity` term catches — the model learns that both a
near-zero and an extreme transfer rate raise risk, only the middle is healthy.
`counterparty_concentration_hhi` catches money cycled between a few accounts.

**SBP regulatory posture?** Alternative-data scoring sits under the SBP's digital
lending and consumer-protection frameworks; adverse-action notices, model
governance (the override rate metric), and a fairness audit on every model
version are table stakes, and this prototype ships all three.

**Unit economics per score?** Inference is a single scaled LightGBM predict plus
a TreeSHAP pass — sub-millisecond on CPU, no GPU, no API cost. The expensive part
is data acquisition (consented wallet + bill pulls), amortised across a
relationship.
