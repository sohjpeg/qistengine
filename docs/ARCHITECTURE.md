# Architecture

> Demonstration model on synthetic data. Not a regulated credit decision.

## Shape

```
                    ┌──────────────────────────┐
   Judge's browser  │  Next.js 14 (App Router)  │   :3000
                    │  src/app  ·  src/components│
                    └────────────┬─────────────┘
                       typed fetch (lib/api.ts)
                                 │  http://localhost:8000
                    ┌────────────▼─────────────┐
                    │  FastAPI  (app/main.py)   │   :8000
                    │  /api/v1/*  ·  /docs      │
                    └────────────┬─────────────┘
        ┌────────────────────────┼────────────────────────┐
        ▼                        ▼                        ▼
┌───────────────┐   ┌────────────────────────┐   ┌────────────────┐
│ services/      │   │ ml/registry.py         │   │ SQLite         │
│  ocr           │   │  model.pkl  (calibrated│   │  applicant     │
│  transaction_  │   │   LightGBM)            │   │  application   │
│   parser       │   │  scaler.pkl            │   │  document      │
│  feature_eng   │   │  explainer.pkl (SHAP)  │   │  score_result  │
│  scorecard     │   │  metadata.json         │   │  decision      │
│  qist_limit    │   └────────────────────────┘   └────────────────┘
│  explainer     │
│  pipeline      │  ← orchestrates all of the above
└───────────────┘
```

## Request flow — `POST /api/v1/applications`

1. **Router** (`routers/applications.py`) masks the CNIC and phone (raw values
   never touch the database), persists `Applicant` + `Application`.
2. **Pipeline** (`services/pipeline.py`):
   - `merge_raw_signals` folds features / bill fields / transaction aggregates
     into one raw dict keyed by `FEATURE_ORDER`.
   - `detect_data_gaps` records any imputed block.
   - `build_feature_vector` produces the ordered 26-vector (imputing medians).
   - `registry.shap_values` → per-feature SHAP (log-odds).
   - `margin = E + Σ SHAP` → `score` via the points-to-double-odds transform.
   - `registry.predict_pd` → calibrated probability (for display + Qist Limit).
   - `explainer.explain` → reason-code ledger (exact points).
   - `qist_limit.compute_qist_limit` → safe installment + haircut breakdown.
   - `feature_engineering.behavioral_metrics` → six radar axes.
   - `synth_monthly_series` reconstructs a 12-month cashflow series if no
     transaction log was uploaded.
3. **Router** persists `ScoreResult`, links `Document` rows, returns the full
   `ApplicationDetail`.

## Offline guarantees

- No network calls after `bootstrap.sh`. Fonts are self-hosted
  (`frontend/public/fonts`, `next/font/local`). No CDN, no remote datasets, no
  LLM on the hot path.
- Model artifacts are built locally by `scripts/train_model.py`; the API reports
  `model_loaded: false` with a clear error instead of crashing if they are
  missing.
- `NEXT_PUBLIC_DEMO_MODE=true` makes the frontend fall back to cached score
  responses (`src/lib/_mock_data.json`, generated from the real pipeline) if the
  backend is unreachable mid-demo.

## Determinism

Every RNG is seeded with 42. `generate_synthetic_data.py` produces a
byte-identical CSV across runs; `train_model.py` produces byte-identical metrics
(`deterministic=True, force_row_wise=True, n_jobs=1`).

## Key files

| Path | Responsibility |
|------|----------------|
| `backend/app/services/feature_engineering.py` | `FEATURE_ORDER` — the one feature contract |
| `backend/app/services/scorecard.py` | PDO scaling, bands |
| `backend/app/services/explainer.py` | SHAP → points, 26 bilingual templates, adverse-action codes |
| `backend/app/services/qist_limit.py` | affordability maths |
| `backend/app/services/pipeline.py` | end-to-end orchestration |
| `backend/app/ml/registry.py` | artifact loading + inference |
| `backend/scripts/*` | data gen, training, fairness audit, sample files |
| `frontend/src/components/ScoreLedger.tsx` | the signature khata-ledger visual |
| `frontend/src/lib/api.ts` | typed client, 30s timeout, one retry, offline envelope |
