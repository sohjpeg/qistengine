#!/usr/bin/env python3
"""Generate a synthetic portfolio of unbanked / micro-merchant credit profiles.

Standalone and deterministic: `python scripts/generate_synthetic_data.py --n 5000 --seed 42`
produces byte-identical output every run.

Design
------
1. Sample raw features per archetype from calibrated distributions.
2. Standardise features, combine in log-odds space with credit-intuitive
   coefficients (utility_on_time_ratio & balance_floor_ratio strongest
   protective; cashflow_volatility & expense_to_income_ratio strongest risk;
   p2p_velocity enters as an explicit quadratic so both extremes are risky).
3. Add archetype intercepts, Gaussian noise (sigma 0.55), sigmoid, Bernoulli.
4. Solve a global intercept so the portfolio default rate lands at ~14%.

Protected attributes (gender, religion, ethnicity, caste, marital_status) and the
load_shedding_flag are emitted for the fairness audit ONLY. They are never used
as model features -- see app/services/feature_engineering.PROTECTED_ATTRIBUTES.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.feature_engineering import FEATURE_ORDER  # noqa: E402

RAW_DIR = BACKEND_ROOT / "data" / "raw"

ARCHETYPES = ["kiryana_merchant", "daily_wage_worker", "home_based_producer", "ride_hailing_driver"]
ARCHETYPE_WEIGHTS = [0.32, 0.28, 0.22, 0.18]

CITIES = [
    "Karachi", "Lahore", "Faisalabad", "Rawalpindi", "Multan",
    "Peshawar", "Quetta", "Hyderabad", "Sialkot", "Gujranwala",
]
# Approximate share of large-city population.
CITY_WEIGHTS = [0.30, 0.22, 0.09, 0.08, 0.07, 0.07, 0.04, 0.05, 0.04, 0.04]

ELECTRICITY_BY_CITY = {
    "Karachi": "K-Electric", "Lahore": "LESCO", "Faisalabad": "FESCO",
    "Rawalpindi": "IESCO", "Multan": "MEPCO", "Peshawar": "PESCO",
    "Quetta": "QESCO", "Hyderabad": "HESCO", "Sialkot": "GEPCO", "Gujranwala": "GEPCO",
}
GAS_SOUTH = {"Karachi", "Hyderabad", "Quetta"}  # SSGC; else SNGPL

WALLETS = ["JazzCash", "EasyPaisa", "SadaPay", "NayaPay", "DigitalKhata"]
WALLET_WEIGHTS = [0.45, 0.35, 0.08, 0.05, 0.07]

CITY_TIER = {
    "Karachi": 1, "Lahore": 1, "Faisalabad": 2, "Rawalpindi": 2, "Multan": 2,
    "Peshawar": 2, "Quetta": 3, "Hyderabad": 2, "Sialkot": 3, "Gujranwala": 3,
}

# --- latent-risk coefficients (log-odds of default per +1 SD of the feature) ---
# Negative => protective (raises score); positive => risk.
# SIGNAL_SCALE is tuned so the trained model lands in the realistic microfinance
# band (ROC-AUC ~0.83-0.87), NOT near-perfect separation. Raise it if test AUC
# drops below 0.78; do not weaken the assertion in train_model.py.
SIGNAL_SCALE = 0.36
# Measurement noise: features are estimated from 3-12 months of thin wallet/bill
# data, so the recorded value is a noisy read of the "true" value that drives
# default. pd_true is computed from the clean values; the model only ever sees
# the noised columns. This is what keeps AUC in the realistic band and gives the
# tree model a small honest edge over a linear baseline (it recovers some of the
# non-linear structure through the noise; the logistic baseline cannot).
MEASUREMENT_NOISE_FRAC = 0.16
BETA = {
    "utility_on_time_ratio": -0.95,
    "utility_avg_days_late": 0.55,
    "utility_bill_volatility": 0.20,
    "utility_months_observed": -0.28,
    "utility_disconnection_events": 0.45,
    "monthly_inflow_pkr": -0.30,
    "monthly_outflow_pkr": 0.18,
    "net_cashflow_ratio": -0.45,
    "cashflow_volatility": 0.85,
    "income_trend_slope": -0.35,
    "zero_balance_days_ratio": 0.55,
    "balance_floor_ratio": -0.90,
    "p2p_velocity": 0.0,  # handled by the quadratic term below
    "p2p_unique_counterparties": -0.22,
    "counterparty_concentration_hhi": 0.40,
    "merchant_inflow_share": -0.25,
    "txn_frequency_monthly": -0.20,
    "mobile_topup_regularity": -0.25,
    "expense_to_income_ratio": 0.80,
    "savings_rate": -0.55,
    "committee_participation": -0.35,
    "wallet_tenure_months": -0.22,
    "business_age_months": -0.30,
    "dependents_count": 0.28,
    "has_fixed_premises": -0.25,
    "sim_tenure_months": -0.18,
}
# Non-linear structure. A plain logistic regression on the raw features cannot
# represent any of these, so they are what gives LightGBM its honest lift.
P2P_QUAD_COEF = 1.15
VOL_BUFFER_INTERACTION = 1.30
LOW_DISCIPLINE_THRESHOLD = 1.40
EXPENSE_STRESS_INTERACTION = 0.95

ARCHETYPE_INTERCEPT = {
    "kiryana_merchant": 0.06,
    "daily_wage_worker": 0.02,
    "home_based_producer": 0.10,
    "ride_hailing_driver": 0.06,
}
NOISE_SIGMA = 0.55
TARGET_DEFAULT_RATE = 0.14


def _lognormal(rng, mean, sigma, size):
    return rng.lognormal(mean=np.log(mean), sigma=sigma, size=size)


def _clip(a, lo, hi):
    return np.clip(a, lo, hi)


def sample_archetype_features(rng: np.random.Generator, archetype: str, n: int) -> dict[str, np.ndarray]:
    """Return raw (un-standardised) feature arrays for `n` profiles of one archetype."""
    f: dict[str, np.ndarray] = {}

    if archetype == "kiryana_merchant":
        base_income = _lognormal(rng, 68000, 0.45, n)
        f["utility_on_time_ratio"] = _clip(rng.beta(4.8, 2.7, n), 0, 1)
        f["utility_avg_days_late"] = _clip(rng.gamma(2.0, 3.5, n), 0, 60)
        f["utility_bill_volatility"] = _clip(rng.normal(0.30, 0.10, n), 0.05, 0.9)
        f["utility_months_observed"] = _clip(rng.integers(8, 13, n).astype(float), 0, 12)
        f["utility_disconnection_events"] = rng.poisson(0.20, n).astype(float)
        f["monthly_inflow_pkr"] = base_income
        f["monthly_outflow_pkr"] = base_income * _clip(rng.normal(0.86, 0.09, n), 0.5, 1.15)
        f["cashflow_volatility"] = _clip(rng.normal(0.33, 0.12, n), 0.05, 1.1)
        f["income_trend_slope"] = rng.normal(0.015, 0.06, n)
        f["zero_balance_days_ratio"] = _clip(rng.beta(2, 8, n), 0, 0.8)
        f["balance_floor_ratio"] = _clip(rng.beta(2.2, 12, n), 0, 0.5)
        f["p2p_velocity"] = _clip(rng.gamma(3.0, 3.0, n), 0, 40)
        f["p2p_unique_counterparties"] = _clip(rng.gamma(3.0, 2.2, n), 1, 25)
        f["counterparty_concentration_hhi"] = _clip(rng.beta(2, 6, n), 0.05, 0.95)
        f["merchant_inflow_share"] = _clip(rng.beta(5, 3, n), 0, 1)
        f["txn_frequency_monthly"] = _clip(rng.gamma(6.0, 12.0, n), 5, 260)
        f["mobile_topup_regularity"] = _clip(rng.beta(4, 3, n), 0, 1)
        f["expense_to_income_ratio"] = _clip(rng.normal(0.83, 0.11, n), 0.3, 1.3)
        f["savings_rate"] = _clip(rng.beta(2.5, 12, n), 0, 0.6)
        f["committee_participation"] = (rng.random(n) < 0.35).astype(float)
        f["wallet_tenure_months"] = _clip(rng.gamma(3.0, 9.0, n), 1, 84)
        f["business_age_months"] = _clip(rng.gamma(3.2, 22.0, n), 2, 300)
        f["dependents_count"] = _clip(rng.poisson(4.0, n), 0, 12).astype(float)
        f["has_fixed_premises"] = (rng.random(n) < 0.9).astype(float)
        f["sim_tenure_months"] = _clip(rng.gamma(3.0, 16.0, n), 2, 160)

    elif archetype == "daily_wage_worker":
        base_income = _lognormal(rng, 34000, 0.5, n)
        f["utility_on_time_ratio"] = _clip(rng.beta(3.7, 2.6, n), 0, 1)
        f["utility_avg_days_late"] = _clip(rng.gamma(2.6, 4.4, n), 0, 60)
        f["utility_bill_volatility"] = _clip(rng.normal(0.32, 0.11, n), 0.05, 1.0)
        f["utility_months_observed"] = _clip(rng.integers(4, 13, n).astype(float), 0, 12)
        f["utility_disconnection_events"] = rng.poisson(0.34, n).astype(float)
        f["monthly_inflow_pkr"] = base_income
        f["monthly_outflow_pkr"] = base_income * _clip(rng.normal(0.90, 0.10, n), 0.6, 1.3)
        f["cashflow_volatility"] = _clip(rng.normal(0.42, 0.14, n), 0.1, 1.3)
        f["income_trend_slope"] = rng.normal(0.0, 0.07, n)
        f["zero_balance_days_ratio"] = _clip(rng.beta(2.8, 5.5, n), 0, 0.95)
        f["balance_floor_ratio"] = _clip(rng.beta(2.2, 13, n), 0, 0.4)
        f["p2p_velocity"] = _clip(rng.gamma(2.0, 2.2, n), 0, 35)
        f["p2p_unique_counterparties"] = _clip(rng.gamma(2.0, 1.8, n), 1, 18)
        f["counterparty_concentration_hhi"] = _clip(rng.beta(3, 4, n), 0.05, 0.97)
        f["merchant_inflow_share"] = _clip(rng.beta(1.4, 6, n), 0, 0.8)
        f["txn_frequency_monthly"] = _clip(rng.gamma(3.0, 6.0, n), 3, 120)
        f["mobile_topup_regularity"] = _clip(rng.beta(2.2, 3.2, n), 0, 1)
        f["expense_to_income_ratio"] = _clip(rng.normal(0.86, 0.11, n), 0.4, 1.5)
        f["savings_rate"] = _clip(rng.beta(1.8, 16, n), 0, 0.4)
        f["committee_participation"] = (rng.random(n) < 0.28).astype(float)
        f["wallet_tenure_months"] = _clip(rng.gamma(2.4, 7.0, n), 1, 72)
        f["business_age_months"] = _clip(rng.gamma(2.0, 12.0, n), 1, 180)
        f["dependents_count"] = _clip(rng.poisson(4.6, n), 0, 13).astype(float)
        f["has_fixed_premises"] = (rng.random(n) < 0.1).astype(float)
        f["sim_tenure_months"] = _clip(rng.gamma(2.6, 12.0, n), 2, 140)

    elif archetype == "home_based_producer":
        base_income = _lognormal(rng, 42000, 0.42, n)
        f["utility_on_time_ratio"] = _clip(rng.beta(4.6, 2.6, n), 0, 1)
        f["utility_avg_days_late"] = _clip(rng.gamma(2.0, 3.4, n), 0, 60)
        f["utility_bill_volatility"] = _clip(rng.normal(0.28, 0.10, n), 0.05, 0.85)
        f["utility_months_observed"] = _clip(rng.integers(7, 13, n).astype(float), 0, 12)
        f["utility_disconnection_events"] = rng.poisson(0.12, n).astype(float)
        f["monthly_inflow_pkr"] = base_income
        f["monthly_outflow_pkr"] = base_income * _clip(rng.normal(0.82, 0.08, n), 0.5, 1.1)
        f["cashflow_volatility"] = _clip(rng.normal(0.33, 0.11, n), 0.05, 1.0)
        f["income_trend_slope"] = rng.normal(0.012, 0.055, n)
        f["zero_balance_days_ratio"] = _clip(rng.beta(2.4, 8, n), 0, 0.7)
        f["balance_floor_ratio"] = _clip(rng.beta(2.1, 12, n), 0, 0.55)
        f["p2p_velocity"] = _clip(rng.gamma(2.2, 2.4, n), 0, 30)
        f["p2p_unique_counterparties"] = _clip(rng.gamma(2.2, 1.6, n), 1, 16)
        f["counterparty_concentration_hhi"] = _clip(rng.beta(2.2, 5, n), 0.05, 0.9)
        f["merchant_inflow_share"] = _clip(rng.beta(3.0, 3.2, n), 0, 1)
        f["txn_frequency_monthly"] = _clip(rng.gamma(3.4, 7.0, n), 4, 130)
        f["mobile_topup_regularity"] = _clip(rng.beta(4.5, 2.6, n), 0, 1)
        f["expense_to_income_ratio"] = _clip(rng.normal(0.76, 0.10, n), 0.3, 1.2)
        f["savings_rate"] = _clip(rng.beta(2.4, 11, n), 0, 0.65)
        f["committee_participation"] = (rng.random(n) < 0.55).astype(float)
        f["wallet_tenure_months"] = _clip(rng.gamma(3.0, 8.0, n), 1, 84)
        f["business_age_months"] = _clip(rng.gamma(2.8, 16.0, n), 2, 220)
        f["dependents_count"] = _clip(rng.poisson(3.6, n), 0, 11).astype(float)
        f["has_fixed_premises"] = (rng.random(n) < 0.35).astype(float)
        f["sim_tenure_months"] = _clip(rng.gamma(3.2, 15.0, n), 2, 150)

    else:  # ride_hailing_driver
        base_income = _lognormal(rng, 56000, 0.4, n)
        f["utility_on_time_ratio"] = _clip(rng.beta(4.5, 2.8, n), 0, 1)
        f["utility_avg_days_late"] = _clip(rng.gamma(2.4, 4.0, n), 0, 60)
        f["utility_bill_volatility"] = _clip(rng.normal(0.31, 0.11, n), 0.05, 0.95)
        f["utility_months_observed"] = _clip(rng.integers(6, 13, n).astype(float), 0, 12)
        f["utility_disconnection_events"] = rng.poisson(0.28, n).astype(float)
        f["monthly_inflow_pkr"] = base_income
        f["monthly_outflow_pkr"] = base_income * _clip(rng.normal(0.9, 0.09, n), 0.55, 1.2)
        f["cashflow_volatility"] = _clip(rng.normal(0.30, 0.10, n), 0.05, 1.0)
        f["income_trend_slope"] = rng.normal(-0.01, 0.07, n)  # fuel-price sensitive
        f["zero_balance_days_ratio"] = _clip(rng.beta(3, 7, n), 0, 0.85)
        f["balance_floor_ratio"] = _clip(rng.beta(2.0, 14, n), 0, 0.45)
        f["p2p_velocity"] = _clip(rng.gamma(3.4, 3.2, n), 0, 45)
        f["p2p_unique_counterparties"] = _clip(rng.gamma(3.6, 2.6, n), 1, 30)
        f["counterparty_concentration_hhi"] = _clip(rng.beta(1.8, 7, n), 0.05, 0.85)
        f["merchant_inflow_share"] = _clip(rng.beta(4.5, 3.5, n), 0, 1)
        f["txn_frequency_monthly"] = _clip(rng.gamma(7.0, 11.0, n), 8, 280)
        f["mobile_topup_regularity"] = _clip(rng.beta(3.8, 3.0, n), 0, 1)
        f["expense_to_income_ratio"] = _clip(rng.normal(0.85, 0.11, n), 0.35, 1.35)
        f["savings_rate"] = _clip(rng.beta(2.2, 12, n), 0, 0.55)
        f["committee_participation"] = (rng.random(n) < 0.3).astype(float)
        f["wallet_tenure_months"] = _clip(rng.gamma(3.2, 9.5, n), 1, 90)
        f["business_age_months"] = _clip(rng.gamma(2.4, 12.0, n), 1, 150)
        f["dependents_count"] = _clip(rng.poisson(4.1, n), 0, 12).astype(float)
        f["has_fixed_premises"] = (rng.random(n) < 0.05).astype(float)
        f["sim_tenure_months"] = _clip(rng.gamma(3.0, 14.0, n), 2, 150)

    # net_cashflow_ratio derived from inflow/outflow
    f["net_cashflow_ratio"] = _clip(
        (f["monthly_inflow_pkr"] - f["monthly_outflow_pkr"]) / np.maximum(f["monthly_inflow_pkr"], 1.0),
        -0.6, 0.8,
    )
    return f


def build_frame(n: int, seed: int) -> tuple[pd.DataFrame, dict]:
    rng = np.random.default_rng(seed)

    counts = rng.multinomial(n, ARCHETYPE_WEIGHTS)
    rows: list[dict] = []
    archetype_labels: list[str] = []

    per_arch_features: dict[str, np.ndarray] = {name: [] for name in FEATURE_ORDER}

    for arch, c in zip(ARCHETYPES, counts):
        if c == 0:
            continue
        feats = sample_archetype_features(rng, arch, int(c))
        for name in FEATURE_ORDER:
            per_arch_features[name].append(np.asarray(feats[name], dtype=float))
        archetype_labels.extend([arch] * int(c))

    data = {name: np.concatenate(per_arch_features[name]) for name in FEATURE_ORDER}
    df = pd.DataFrame(data)
    df["archetype"] = archetype_labels

    # Shuffle so archetypes are interleaved (stable given seed).
    perm = rng.permutation(len(df))
    df = df.iloc[perm].reset_index(drop=True)

    # --- context columns ---
    df["city"] = rng.choice(CITIES, size=len(df), p=CITY_WEIGHTS)
    df["city_tier"] = df["city"].map(CITY_TIER).astype(int)
    df["electricity_provider"] = df["city"].map(ELECTRICITY_BY_CITY)
    df["gas_provider"] = np.where(df["city"].isin(GAS_SOUTH), "SSGC", "SNGPL")
    df["wallet_provider"] = rng.choice(WALLETS, size=len(df), p=WALLET_WEIGHTS)

    # --- load-shedding effect: 12% have 1-2 anomalously low electricity months ---
    df["load_shedding_flag"] = (rng.random(len(df)) < 0.12).astype(int)
    # It nudges bill volatility up but must NOT be punished by the model, so it does
    # not enter the latent risk score at all.
    df.loc[df["load_shedding_flag"] == 1, "utility_bill_volatility"] = _clip(
        df.loc[df["load_shedding_flag"] == 1, "utility_bill_volatility"] + rng.uniform(0.05, 0.2, int(df["load_shedding_flag"].sum())),
        0.05, 1.2,
    )

    # --- protected attributes (fairness audit ONLY; never model features) ---
    # home_based_producer skews female by construction of the archetype.
    p_female = df["archetype"].map(
        {"home_based_producer": 0.62, "kiryana_merchant": 0.20,
         "daily_wage_worker": 0.12, "ride_hailing_driver": 0.04}
    ).to_numpy()
    df["gender"] = np.where(rng.random(len(df)) < p_female, "female", "male")
    df["religion"] = rng.choice(
        ["muslim", "christian", "hindu", "other"], size=len(df), p=[0.94, 0.03, 0.02, 0.01]
    )
    df["ethnicity"] = rng.choice(
        ["punjabi", "sindhi", "pashtun", "muhajir", "baloch", "saraiki"],
        size=len(df), p=[0.42, 0.14, 0.15, 0.14, 0.05, 0.10],
    )
    df["caste"] = rng.choice(["A", "B", "C", "D"], size=len(df), p=[0.35, 0.3, 0.2, 0.15])
    df["marital_status"] = rng.choice(
        ["married", "single", "widowed", "divorced"], size=len(df), p=[0.7, 0.22, 0.05, 0.03]
    )

    # --- latent risk in log-odds space ---
    z = pd.DataFrame(index=df.index)
    means: dict[str, float] = {}
    stds: dict[str, float] = {}
    for name in FEATURE_ORDER:
        col = df[name].astype(float)
        m, s = float(col.mean()), float(col.std(ddof=0)) or 1.0
        means[name], stds[name] = m, s
        z[name] = (col - m) / s

    zp2p = z["p2p_velocity"].to_numpy()
    zvol = z["cashflow_volatility"].to_numpy()
    zbuf = z["balance_floor_ratio"].to_numpy()
    zdisc = z["utility_on_time_ratio"].to_numpy()
    zexp = z["expense_to_income_ratio"].to_numpy()
    ztrend = z["income_trend_slope"].to_numpy()

    linear = np.zeros(len(df))
    for name, coef in BETA.items():
        linear += SIGNAL_SCALE * coef * z[name].to_numpy()
    # explicit non-monotonic p2p term (both tails riskier)
    linear += SIGNAL_SCALE * P2P_QUAD_COEF * (zp2p**2)
    # volatility hurts more when the cash buffer is thin
    linear += SIGNAL_SCALE * VOL_BUFFER_INTERACTION * np.maximum(zvol, 0.0) * np.maximum(-zbuf, 0.0)
    # discipline kink: below ~1 SD of on-time ratio, risk accelerates
    linear += SIGNAL_SCALE * LOW_DISCIPLINE_THRESHOLD * np.maximum(-zdisc - 1.0, 0.0)
    # expense stress compounds with a declining income trend
    linear += SIGNAL_SCALE * EXPENSE_STRESS_INTERACTION * np.maximum(zexp, 0.0) * np.maximum(-ztrend, 0.0)
    # archetype intercepts
    linear += df["archetype"].map(ARCHETYPE_INTERCEPT).to_numpy()
    # gaussian noise
    linear += rng.normal(0.0, NOISE_SIGMA, len(df))

    # solve global intercept b so mean(sigmoid(linear + b)) ~= TARGET_DEFAULT_RATE
    lo, hi = -12.0, 12.0
    for _ in range(80):
        mid = (lo + hi) / 2
        rate = float(np.mean(1.0 / (1.0 + np.exp(-(linear + mid)))))
        if rate > TARGET_DEFAULT_RATE:
            hi = mid
        else:
            lo = mid
    intercept = (lo + hi) / 2

    pd_true = 1.0 / (1.0 + np.exp(-(linear + intercept)))
    df["pd_true"] = pd_true
    df["default_flag"] = (rng.random(len(df)) < pd_true).astype(int)

    # --- measurement noise: pd_true is fixed from clean values above; now noise
    #     the recorded feature columns the model will train and score on. ---
    binary_feats = {"committee_participation", "has_fixed_premises"}
    integer_feats = {
        "utility_months_observed", "utility_disconnection_events",
        "p2p_unique_counterparties", "dependents_count",
    }
    ranges = {
        "utility_on_time_ratio": (0, 1), "utility_avg_days_late": (0, 60),
        "utility_bill_volatility": (0.05, 1.3), "utility_months_observed": (0, 12),
        "utility_disconnection_events": (0, 8), "net_cashflow_ratio": (-0.6, 0.8),
        "cashflow_volatility": (0.05, 1.4), "income_trend_slope": (-0.4, 0.4),
        "zero_balance_days_ratio": (0, 1), "balance_floor_ratio": (0, 0.7),
        "counterparty_concentration_hhi": (0.03, 0.98), "merchant_inflow_share": (0, 1),
        "mobile_topup_regularity": (0, 1), "expense_to_income_ratio": (0.2, 1.6),
        "savings_rate": (0, 0.7),
    }
    for name in FEATURE_ORDER:
        col = df[name].to_numpy(dtype=float)
        if name in binary_feats:
            flip = rng.random(len(df)) < 0.05
            col = np.where(flip, 1.0 - col, col)
        else:
            sd = float(np.std(col)) or 1.0
            col = col + rng.normal(0.0, MEASUREMENT_NOISE_FRAC * sd, len(df))
            if name in integer_feats:
                col = np.round(col)
            lo_hi = ranges.get(name)
            if lo_hi:
                col = np.clip(col, lo_hi[0], lo_hi[1])
            elif name.endswith("_pkr") or name.endswith("_months"):
                col = np.clip(col, 0.0, None)
        df[name] = col
    # keep net_cashflow_ratio consistent with the noised inflow/outflow
    df["net_cashflow_ratio"] = np.clip(
        (df["monthly_inflow_pkr"] - df["monthly_outflow_pkr"]) / np.maximum(df["monthly_inflow_pkr"], 1.0),
        -0.6, 0.8,
    )

    meta = {
        "n": int(len(df)),
        "seed": seed,
        "base_default_rate": float(df["default_flag"].mean()),
        "target_default_rate": TARGET_DEFAULT_RATE,
        "signal_scale": SIGNAL_SCALE,
        "noise_sigma": NOISE_SIGMA,
        "solved_intercept": float(intercept),
        "feature_means": means,
        "feature_stds": stds,
        "feature_medians": {name: float(df[name].median()) for name in FEATURE_ORDER},
        "archetype_counts": {a: int((df["archetype"] == a).sum()) for a in ARCHETYPES},
    }
    return df, meta


def data_dictionary() -> dict:
    return {
        "features": {
            "utility_on_time_ratio": "Fraction of utility bills paid on/before due date, last 12 months (0-1).",
            "utility_avg_days_late": "Mean days past due, clipped 0-60.",
            "utility_bill_volatility": "Coefficient of variation of monthly billed amount, seasonally adjusted.",
            "utility_months_observed": "Number of billing months observed, 0-12 (data-depth signal).",
            "utility_disconnection_events": "Count of service disconnections in 12 months.",
            "monthly_inflow_pkr": "Mean monthly credit (inflow) in PKR.",
            "monthly_outflow_pkr": "Mean monthly debit (outflow) in PKR.",
            "net_cashflow_ratio": "(inflow - outflow) / inflow.",
            "cashflow_volatility": "Std of monthly net divided by mean monthly inflow.",
            "income_trend_slope": "OLS slope of monthly inflow over 6 months, normalised by mean inflow.",
            "zero_balance_days_ratio": "Days with closing balance < PKR 200, divided by days observed.",
            "balance_floor_ratio": "10th-percentile daily balance / mean monthly inflow.",
            "p2p_velocity": "P2P transfers per active month (non-monotonic risk).",
            "p2p_unique_counterparties": "Distinct counterparties per month.",
            "counterparty_concentration_hhi": "Herfindahl index over counterparty volume share (0-1).",
            "merchant_inflow_share": "Share of inflow tagged merchant / QR receipts.",
            "txn_frequency_monthly": "Total transactions per month.",
            "mobile_topup_regularity": "1 - CV of days between mobile top-ups.",
            "expense_to_income_ratio": "Essential outflow / inflow.",
            "savings_rate": "Mean end-of-month balance / monthly inflow.",
            "committee_participation": "Binary: ROSCA / committee (BC) contributions detected.",
            "wallet_tenure_months": "Months the mobile wallet has been active.",
            "business_age_months": "Months the business has operated.",
            "dependents_count": "Number of dependents.",
            "has_fixed_premises": "Binary: operates from fixed business premises.",
            "sim_tenure_months": "Months the current SIM has been registered.",
        },
        "context_columns": {
            "archetype": "One of: " + ", ".join(ARCHETYPES),
            "city": "One of 10 large Pakistani cities.",
            "city_tier": "1 (Karachi/Lahore), 2, or 3.",
            "electricity_provider": "DISCO serving the city.",
            "gas_provider": "SSGC (south) or SNGPL (north).",
            "wallet_provider": "Mobile wallet / ledger app.",
            "load_shedding_flag": "1 if 1-2 months of anomalously low electricity use; EXCLUDED from features.",
        },
        "protected_attributes": {
            "gender": "female / male -- fairness audit ONLY, never a feature.",
            "religion": "fairness audit ONLY, never a feature.",
            "ethnicity": "fairness audit ONLY, never a feature.",
            "caste": "fairness audit ONLY, never a feature.",
            "marital_status": "fairness audit ONLY, never a feature.",
        },
        "label": {
            "default_flag": "1 if the profile defaulted (Bernoulli draw from pd_true).",
            "pd_true": "Latent probability of default used to generate the label.",
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=str, default=str(RAW_DIR / "synthetic_profiles.csv"))
    args = ap.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    df, meta = build_frame(args.n, args.seed)

    out_path = Path(args.out)
    df.to_csv(out_path, index=False, float_format="%.6f")

    dd = data_dictionary()
    dd["_generation_meta"] = meta
    (RAW_DIR / "data_dictionary.json").write_text(json.dumps(dd, indent=2), encoding="utf-8")

    print(f"[generate] wrote {len(df)} profiles -> {out_path}")
    print(f"[generate] base default rate: {meta['base_default_rate']:.4f}")
    print(f"[generate] archetype counts: {meta['archetype_counts']}")
    print(f"[generate] data dictionary -> {RAW_DIR / 'data_dictionary.json'}")


if __name__ == "__main__":
    main()
