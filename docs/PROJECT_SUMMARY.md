# QistEngine — Project Summary

**Team:** [Sohaib Amir Bukhari](https://www.linkedin.com/in/sohaib-amir-7a89161a6/) · [Asma Imran](https://www.linkedin.com/in/asmaimran/) — BS Computer Science, NUST
**Repository:** https://github.com/sohjpeg/qistengine (public · runs fully offline · two commands)

---

## What it does

QistEngine is an **alternative credit-scoring engine** for the ~100 million adults
in Pakistan who sit outside the formal banking system — kiryana shopkeepers,
tailors, home-based cooks, daily-wage earners, ride-hailing drivers. A credit
bureau has nothing on them because they were never given a first loan to build a
history with.

From **one utility bill and one mobile-wallet statement**, QistEngine produces:

- a **300–850 score** and a risk band;
- a **calibrated probability of default** — a real frequency, not just a ranking;
- an **exact reason-code ledger** that reads like a shopkeeper's *khata* and sums,
  line by line, to the score — so a loan officer can audit the decision by hand;
- a **safe monthly "Qist" (installment)** sized to the applicant's actual cashflow,
  which is a different question from the score;
- a **what-if panel** that re-scores live as the officer moves a lever, turning a
  black-box number into a conversation with the applicant;
- an **adverse-action notice** and a **printable credit memo** for the branch file.

## Who it's for

A microfinance / BNPL loan officer at the branch counter. The interface is built
as a working underwriting tool — an applicant portal, an underwriting queue, an
applicant decision page, and a portfolio-analytics view with the model card and a
fairness audit — not a demo dashboard.

## What we built

- **Ingestion** — an OCR cascade for the bill (PDF text layer → Tesseract →
  clearly-labelled fallback, never fabricated) and a statement parser that
  normalises JazzCash / EasyPaisa / hand-kept *Digital Khata* exports, tolerant of
  preamble rows, split debit/credit columns and `Rs`/comma formatting, with
  Urdu-and-English transaction classification.
- **26 behavioural features** — cashflow level and volatility, buffer, utility
  payment discipline, savings behaviour, business tenure, committee participation.
  Gender, religion, ethnicity, caste, marital status and area proxies are
  **forbidden as features** — they exist in the synthetic data only so the
  fairness audit can run.
- **A calibrated LightGBM scorecard** — isotonic calibration; a
  points-to-double-the-odds scaling where the score is affine in log-odds and SHAP
  values are additive in log-odds, which is why the ledger foots exactly.
  Test ROC-AUC **0.819**, KS **0.488**, Gini **0.638**, Brier **0.099**; beats a
  transparent logistic baseline and separates the tails far better.
- **A fairness audit** that runs on every training pass — a four-fifths (80%) rule
  check across groups. Gender and city tier pass; two livelihood groups
  (daily-wage, ride-hailing) are flagged as genuine cashflow risk, with documented
  mitigations.
- **A responsible-AI posture throughout** — a "demonstration model / not a
  regulated credit decision" disclaimer on every decision surface, adverse-action
  codes for every decline, fully deterministic (seed 42, byte-identical metrics on
  a re-run), and **no network on the hot path** — no CDN, no LLM call. It trains
  and serves on a judge's laptop.

## Honest about the data

This is a prototype. The model is trained on a **synthetic portfolio** generated
from a documented data-generating process (archetype cashflow distributions,
non-linear repayment dynamics, measurement noise) because no lender hands a
student team its repayment book. Everything else — the feature engineering, the
scorecard maths, the calibration, the fairness audit, the ingestion pipeline, the
officer UI — is production-shaped. A pilot replaces exactly one thing: the
synthetic outcomes, swapped for a partner institution's real repayment history,
then recalibrated.

## Running it

```
git clone https://github.com/sohjpeg/qistengine.git && cd qistengine && bash run-dev.sh
```

First run bootstraps itself (Python venv, synthetic data, model training, npm
install, seed) in ~4 minutes, then starts both servers. App on
`http://localhost:3000`, API docs on `http://localhost:8000/docs`. Six demo
profiles are built in — no data to upload. **34 backend tests pass; every
dependency is pinned to an exact version.**

*Stack: FastAPI · SQLModel · SQLite · Next.js 14 (App Router) · LightGBM · SHAP.*
