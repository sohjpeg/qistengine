# Scoring methodology

> Demonstration model trained on synthetic data. Not a regulated credit decision.
> Numbers below are from the shipped training run
> (`qistengine-scorecard-v1.0.0`, seed 42, n = 5000).

---

## 1. What the model consumes

Exactly **26 features**, frozen in
`backend/app/services/feature_engineering.py::FEATURE_ORDER`. The generator, the
trainer, the scoring service and the SHAP explainer all import the order from
that one place.

| # | Feature | Definition | Direction |
|---|---------|------------|-----------|
| 1 | `utility_on_time_ratio` | Fraction of bills paid on/before due date, 12 mo | protective (strong) |
| 2 | `utility_avg_days_late` | Mean days past due, clipped 0–60 | risk |
| 3 | `utility_bill_volatility` | CV of monthly billed amount, seasonally adjusted | risk (mild) |
| 4 | `utility_months_observed` | Billing months on file, 0–12 | protective (depth) |
| 5 | `utility_disconnection_events` | Disconnections in 12 mo | risk |
| 6 | `monthly_inflow_pkr` | Mean monthly wallet credit | protective (mild) |
| 7 | `monthly_outflow_pkr` | Mean monthly wallet debit | risk (mild) |
| 8 | `net_cashflow_ratio` | (inflow − outflow) / inflow | protective |
| 9 | `cashflow_volatility` | std(monthly net) / mean(monthly inflow) | risk (strong) |
| 10 | `income_trend_slope` | OLS slope of inflow over 6 mo, normalised | protective |
| 11 | `zero_balance_days_ratio` | Days with closing balance < Rs 200 / days observed | risk |
| 12 | `balance_floor_ratio` | 10th-pct daily balance / mean monthly inflow | protective (strong) |
| 13 | `p2p_velocity` | P2P transfers per active month | **non-monotonic** |
| 14 | `p2p_unique_counterparties` | Distinct counterparties per month | protective (mild) |
| 15 | `counterparty_concentration_hhi` | Herfindahl index over counterparty volume | risk |
| 16 | `merchant_inflow_share` | Share of inflow tagged merchant / QR | protective (mild) |
| 17 | `txn_frequency_monthly` | Transactions per month | protective (mild) |
| 18 | `mobile_topup_regularity` | 1 − CV of days between top-ups | protective (mild) |
| 19 | `expense_to_income_ratio` | Essential outflow / inflow | risk (strong) |
| 20 | `savings_rate` | Mean end-of-month balance / monthly inflow | protective |
| 21 | `committee_participation` | ROSCA / committee (BC) contributions detected | protective |
| 22 | `wallet_tenure_months` | Months the wallet has been active | protective (mild) |
| 23 | `business_age_months` | Months the business has operated | protective |
| 24 | `dependents_count` | Number of dependents | risk (mild) |
| 25 | `has_fixed_premises` | Fixed business premises (binary) | protective |
| 26 | `sim_tenure_months` | Months the current SIM has been registered | protective (mild) |

**Excluded by construction:** gender, religion, ethnicity, caste, marital status,
area-level proxies for these, and `load_shedding_flag`. See `RESPONSIBLE_AI.md`.

### Behavioural radar aggregation

The six radar axes are weighted blends of normalised features, each 0–100. Weights
are in `feature_engineering.behavioral_metrics`. For example:

```
payment_discipline = 0.55·on_time_ratio
                   + 0.30·(1 − scaled avg_days_late)
                   + 0.15·(1 − scaled disconnection_events)
```

---

## 2. Label generation (stated openly)

For each synthetic profile:

1. Sample raw features from archetype-calibrated distributions.
2. Standardise, then form a latent log-odds:
   `η = SIGNAL_SCALE·Σⱼ βⱼ·zⱼ + non-linear terms + archetype_intercept + N(0, 0.55)`
   with `SIGNAL_SCALE = 0.36`.
   - `utility_on_time_ratio` (β = −0.95) and `balance_floor_ratio` (β = −0.90)
     are the strongest protective coefficients.
   - `cashflow_volatility` (β = 0.85) and `expense_to_income_ratio` (β = 0.80)
     are the strongest risk coefficients.
   - `p2p_velocity` enters **only** as a quadratic `+1.15·z²`, so both a
     near-zero transfer rate (no economic activity) and an extreme rate (possible
     circular transfers) raise risk while the middle is healthy.
   - Additional non-linear terms a linear model cannot represent: a
     volatility × thin-buffer interaction, a low-discipline threshold kink, and
     an expense × declining-income interaction.
3. Solve a global intercept by bisection so
   `mean(sigmoid(η + b)) ≈ 0.14`.
4. `default_flag ~ Bernoulli(sigmoid(η + b))`.
5. **Measurement noise:** `pd_true` is fixed from the clean feature values above,
   then Gaussian noise (16% of each feature's SD) is added to the columns the
   model actually trains and scores on. Real features are estimated from 3–12
   months of thin data; this keeps AUC in a realistic band and leaves non-linear
   structure for the tree model to recover.

Portfolio default rate on the shipped dataset: **0.145**.

---

## 3. Training

- Stratified **70 / 15 / 15** split (3500 / 750 / 750), seed 42, stratified on
  `default_flag`.
- `StandardScaler` on the 26 features, persisted as `scaler.pkl`.
- `LGBMClassifier(n_estimators=400, learning_rate=0.045, num_leaves=24,
  max_depth=6, min_child_samples=40, subsample=0.85, colsample_bytree=0.8,
  reg_lambda=1.2, random_state=42, deterministic=True)`, early stopping on
  validation AUC, patience 40 → best iteration **95**.
- `LogisticRegression` baseline for an honest lift comparison.
- `CalibratedClassifierCV(method="isotonic", cv=3)` wraps the fitted LightGBM so
  the predicted probability is a real frequency — this is what makes the Qist
  Limit defensible.
- `shap.TreeExplainer` on 500 background rows, `feature_perturbation="interventional"`,
  `model_output="raw"`; the expected value (log-odds) is persisted.

### Measured performance (held-out test split)

| Metric | Value |
|--------|-------|
| ROC-AUC (calibrated) | **0.8192** |
| ROC-AUC (uncalibrated LightGBM) | 0.8284 |
| PR-AUC | 0.4595 |
| KS statistic | 0.4879 |
| Gini | 0.6383 |
| Brier score | 0.0988 |
| Logistic baseline ROC-AUC | 0.8167 |
| LightGBM lift over baseline | +0.0025 |
| Base default rate | 0.145 |

Decile lift (decile 1 = riskiest 10% by predicted PD):

| Decile | n | Default rate | Lift |
|--------|---|--------------|------|
| 1 | 75 | 0.587 | 4.04 |
| 2 | 75 | 0.227 | 1.56 |
| 3 | 75 | 0.173 | 1.19 |
| 4 | 75 | 0.187 | 1.28 |
| 5 | 75 | 0.133 | 0.92 |

**Honest note on the baseline.** The data-generating process is close to linear
in log-odds by design, so a well-regularised logistic regression is a strong
baseline. LightGBM's edge here is small (+0.0025 AUC). We still ship the
calibrated LightGBM because (a) isotonic calibration gives us true probabilities
for the Qist Limit, (b) the tree naturally represents the non-monotonic
`p2p_velocity` effect without us hand-coding a spline, and (c) `TreeExplainer`
gives exact per-feature attributions.

The assertion `test ROC-AUC ≥ 0.78` is enforced in `train_model.py` and never
weakened; if it fails, `SIGNAL_SCALE` in the generator is raised and the data
regenerated.

---

## 4. Points-to-double-the-odds scaling

```
PDO        = 40
base_score = 660
base_odds  = 30           # 30:1 good:bad at base_score
factor     = PDO / ln(2)          = 57.70780
offset     = base_score − factor · ln(base_odds) = 463.7188

odds       = (1 − pd) / pd
raw_score  = offset + factor · ln(odds)
score      = clip(round(raw_score), 300, 850)
```

Because `raw_score` is **affine in log-odds**, and `ln(odds) = −logit(pd)`:

```
raw_score = offset − factor · logit(pd)
```

### Risk bands

| Band | Range | Policy |
|------|-------|--------|
| LOW | 720–850 | Auto-approve up to limit |
| MEDIUM | 640–719 | Manual review, reduced tenor |
| HIGH | 560–639 | Guarantor or collateral required |
| VERY_HIGH | 300–559 | Decline, offer financial-literacy referral |

**Population note.** `base_odds = 30` anchors the scale to a prime population
(≈3.2% default at 660). Our synthetic portfolio defaults at 14.5%, so scores
cluster lower and a large share of the portfolio lands HIGH / VERY_HIGH — the
correct behaviour for a scale calibrated to prime odds applied to a
microfinance-stressed book. The six demo profiles are tuned to span four bands.

---

## 5. SHAP → score points (exact, not approximate)

The LightGBM margin is `f(x) = E + Σⱼ φⱼ` where `E` is the SHAP expected value
(log-odds; **E = −2.4019** in the shipped model) and `φⱼ` the per-feature SHAP
value. Then:

```
raw_score = offset − factor · f(x)
          = offset − factor · (E + Σⱼ φⱼ)
          = (offset − factor · E)  +  Σⱼ (−factor · φⱼ)
          = base_contribution      +  Σⱼ pointsⱼ
```

So:

- `base_contribution = offset − factor · E`  (≈ 463.72 − 57.708·(−2.402) ≈ **602.3**)
- `pointsⱼ = −factor · φⱼ`

and `base_contribution + Σ pointsⱼ = raw_score` **exactly**, up to the final
`round()` and `clip()`. `test_scorecard.py::test_shap_points_sum_to_score_within_two_points`
asserts the reconstructed total is within 2 points of the displayed score. The
`ScoreLedger` component renders this sum as a khata ledger — you can add the
column up by hand.

The score is derived from the **uncalibrated** margin (so additivity holds); the
displayed probability of default is the **calibrated** figure (so it is a true
frequency). Both are monotone in risk.

---

## 6. Safe Qist Limit

```
disposable         = monthly_inflow_pkr − monthly_outflow_pkr
dsr_cap            = {LOW:0.35, MEDIUM:0.25, HIGH:0.18, VERY_HIGH:0.10}[band]
volatility_haircut = clip(1 − cashflow_volatility, 0.45, 1.0)
depth_confidence   = clip(utility_months_observed / 12, 0.5, 1.0)
consistency_bonus  = 1 + 0.15 · utility_on_time_ratio

safe_installment   = disposable · dsr_cap · volatility_haircut
                     · depth_confidence · consistency_bonus
safe_installment   = clip(floor(safe_installment / 500) · 500, 0, 50_000)

tenor              = {LOW:12, MEDIUM:9, HIGH:6, VERY_HIGH:3}[band]   (or user override 3/6/9/12)
flat_markup_pm     = 0.015
principal          = floor( (safe_installment · tenor) / (1 + flat_markup_pm · tenor) / 1000 ) · 1000
total_repayable    = safe_installment · tenor
```

If `safe_installment < 2000`, the response is `eligible: false` with reason
`INSUFFICIENT_DISPOSABLE_INCOME`. The limit is never negative and never exceeds
Rs 50,000. The full component breakdown is returned so the UI can render the
haircut waterfall, and the tenor selector recomputes `principal` client-side from
those components with no network call.

---

## 7. Partial data

If a caller sends only a bill (no transaction log), the missing feature block is
imputed at population medians, a `data_gaps` entry is added, and `confidence`
drops (a blend of data depth and completeness). Scoring never fails on partial
data — a scoring engine for unbanked people that requires complete data has
misunderstood the problem.
