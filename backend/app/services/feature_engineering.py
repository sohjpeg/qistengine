"""The single source of truth for the QistEngine feature contract.

`FEATURE_ORDER` is the frozen 26-feature list. The synthetic-data generator, the
training script, the scoring service, and the SHAP explainer all import the order
from here. It is never re-declared anywhere else.

Every feature is derivable from (a) a utility bill and (b) a wallet transaction
log. Gender, religion, ethnicity, caste, marital status, and area-level proxies
for these are deliberately absent -- see docs/RESPONSIBLE_AI.md.
"""
from __future__ import annotations

from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# The frozen feature contract
# ---------------------------------------------------------------------------
FEATURE_ORDER: list[str] = [
    # --- Utility discipline ---
    "utility_on_time_ratio",
    "utility_avg_days_late",
    "utility_bill_volatility",
    "utility_months_observed",
    "utility_disconnection_events",
    # --- Cashflow health ---
    "monthly_inflow_pkr",
    "monthly_outflow_pkr",
    "net_cashflow_ratio",
    "cashflow_volatility",
    "income_trend_slope",
    "zero_balance_days_ratio",
    "balance_floor_ratio",
    # --- Transaction behaviour ---
    "p2p_velocity",
    "p2p_unique_counterparties",
    "counterparty_concentration_hhi",
    "merchant_inflow_share",
    "txn_frequency_monthly",
    "mobile_topup_regularity",
    "expense_to_income_ratio",
    "savings_rate",
    "committee_participation",
    # --- Stability ---
    "wallet_tenure_months",
    "business_age_months",
    "dependents_count",
    "has_fixed_premises",
    "sim_tenure_months",
]

N_FEATURES = len(FEATURE_ORDER)
assert N_FEATURES == 26, "The feature contract must contain exactly 26 features."

FEATURE_CATEGORY: dict[str, str] = {
    **{f: "utility_discipline" for f in FEATURE_ORDER[0:5]},
    **{f: "cashflow_health" for f in FEATURE_ORDER[5:12]},
    **{f: "transaction_behaviour" for f in FEATURE_ORDER[12:21]},
    **{f: "stability" for f in FEATURE_ORDER[21:26]},
}

# Features that are forbidden as model inputs. They may appear in the synthetic
# dataset only so the fairness audit can measure disparate impact against them.
PROTECTED_ATTRIBUTES: list[str] = [
    "gender",
    "religion",
    "ethnicity",
    "caste",
    "marital_status",
]

# Operational flags that must never be treated as features (e.g. load-shedding).
NON_FEATURE_FLAGS: list[str] = [
    "load_shedding_flag",
    "default_flag",
]

# ---------------------------------------------------------------------------
# Population medians -- used to impute a missing data block for partial applicants.
# These are the medians of the shipped synthetic portfolio (seed 42, n=5000) and
# are regenerated into data_dictionary.json by the generator; kept here so the API
# runs even if that file is absent.
# ---------------------------------------------------------------------------
POPULATION_MEDIANS: dict[str, float] = {
    "utility_on_time_ratio": 0.75,
    "utility_avg_days_late": 6.0,
    "utility_bill_volatility": 0.28,
    "utility_months_observed": 12.0,
    "utility_disconnection_events": 0.0,
    "monthly_inflow_pkr": 52000.0,
    "monthly_outflow_pkr": 43000.0,
    "net_cashflow_ratio": 0.16,
    "cashflow_volatility": 0.34,
    "income_trend_slope": 0.01,
    "zero_balance_days_ratio": 0.18,
    "balance_floor_ratio": 0.08,
    "p2p_velocity": 9.0,
    "p2p_unique_counterparties": 6.0,
    "counterparty_concentration_hhi": 0.30,
    "merchant_inflow_share": 0.35,
    "txn_frequency_monthly": 46.0,
    "mobile_topup_regularity": 0.55,
    "expense_to_income_ratio": 0.78,
    "savings_rate": 0.12,
    "committee_participation": 0.0,
    "wallet_tenure_months": 22.0,
    "business_age_months": 48.0,
    "dependents_count": 4.0,
    "has_fixed_premises": 0.0,
    "sim_tenure_months": 40.0,
}

# Which features come from the utility bill vs. the transaction log. Used to decide
# which block to impute when a caller submits partial data.
UTILITY_BLOCK: list[str] = FEATURE_ORDER[0:5]
TRANSACTION_BLOCK: list[str] = FEATURE_ORDER[5:21]
STABILITY_BLOCK: list[str] = FEATURE_ORDER[21:26]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _f(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        if isinstance(x, bool):
            return 1.0 if x else 0.0
        return float(x)
    except (TypeError, ValueError):
        return default


def _clip01(x: float) -> float:
    return float(min(1.0, max(0.0, x)))


def _scale(value: float, lo: float, hi: float, invert: bool = False) -> float:
    """Linear-map value from [lo, hi] onto [0, 1], clipped. Optionally inverted."""
    if hi == lo:
        return 0.0
    t = (value - lo) / (hi - lo)
    t = _clip01(t)
    return 1.0 - t if invert else t


def build_feature_vector(raw: dict[str, Any]) -> np.ndarray:
    """Assemble an ordered float vector from a raw signal dict.

    Missing keys fall back to the population median so scoring never fails on
    partial data. Callers should use `detect_data_gaps` first to report what was
    imputed.
    """
    vec = np.zeros(N_FEATURES, dtype=np.float64)
    for i, name in enumerate(FEATURE_ORDER):
        if name in raw and raw[name] is not None:
            vec[i] = _f(raw[name], POPULATION_MEDIANS[name])
        else:
            vec[i] = POPULATION_MEDIANS[name]
    return vec


def detect_data_gaps(raw: dict[str, Any]) -> list[dict[str, str]]:
    """Return a list describing which feature blocks were imputed."""
    gaps: list[dict[str, str]] = []
    blocks = {
        "utility_bill": UTILITY_BLOCK,
        "transaction_log": TRANSACTION_BLOCK,
        "stability_profile": STABILITY_BLOCK,
    }
    for label, block in blocks.items():
        present = [f for f in block if raw.get(f) is not None]
        if not present:
            gaps.append(
                {
                    "block": label,
                    "detail": f"No {label.replace('_', ' ')} supplied; "
                    f"{len(block)} features imputed at population medians.",
                }
            )
        elif len(present) < len(block):
            missing = [f for f in block if raw.get(f) is None]
            gaps.append(
                {
                    "block": label,
                    "detail": f"Partial {label.replace('_', ' ')}: imputed "
                    + ", ".join(missing),
                }
            )
    return gaps


def confidence_from_gaps(gaps: list[dict[str, str]], utility_months_observed: float) -> float:
    """Blend data-depth and completeness into a 0-1 confidence figure."""
    depth = _scale(utility_months_observed, 3.0, 12.0)
    completeness = 1.0 - 0.22 * len([g for g in gaps if g["detail"].startswith("No")])
    completeness -= 0.06 * len([g for g in gaps if g["detail"].startswith("Partial")])
    return round(_clip01(0.35 + 0.4 * depth + 0.4 * _clip01(completeness) - 0.15), 2)


# ---------------------------------------------------------------------------
# Behavioural radar aggregation (the six axes on BehaviorRadar).
# Each axis is a weighted blend of normalised raw features, scored 0-100.
# The weights and normalisation ranges are documented in docs/SCORING_METHODOLOGY.md.
# ---------------------------------------------------------------------------
def behavioral_metrics(raw: dict[str, Any]) -> dict[str, int]:
    g = lambda k: _f(raw.get(k), POPULATION_MEDIANS[k])  # noqa: E731

    payment_discipline = (
        0.55 * g("utility_on_time_ratio")
        + 0.30 * _scale(g("utility_avg_days_late"), 0, 30, invert=True)
        + 0.15 * _scale(g("utility_disconnection_events"), 0, 3, invert=True)
    )

    cashflow_stability = (
        0.40 * _scale(g("cashflow_volatility"), 0.1, 0.9, invert=True)
        + 0.25 * _scale(g("net_cashflow_ratio"), -0.1, 0.4)
        + 0.20 * _scale(g("balance_floor_ratio"), 0.0, 0.25)
        + 0.15 * _scale(g("income_trend_slope"), -0.15, 0.15)
    )

    transaction_activity = (
        0.35 * _scale(g("txn_frequency_monthly"), 5, 120)
        + 0.25 * _scale(g("p2p_velocity"), 1, 25)
        + 0.25 * _scale(g("merchant_inflow_share"), 0.0, 0.8)
        + 0.15 * _scale(g("p2p_unique_counterparties"), 1, 15)
    )

    savings_behavior = (
        0.40 * _scale(g("savings_rate"), 0.0, 0.35)
        + 0.30 * _scale(g("zero_balance_days_ratio"), 0.0, 0.6, invert=True)
        + 0.15 * _clip01(g("committee_participation"))
        + 0.15 * _scale(g("balance_floor_ratio"), 0.0, 0.25)
    )

    business_maturity = (
        0.35 * _scale(g("business_age_months"), 0, 120)
        + 0.30 * _scale(g("wallet_tenure_months"), 0, 60)
        + 0.20 * _scale(g("utility_months_observed"), 0, 12)
        + 0.15 * _clip01(g("has_fixed_premises"))
    )

    network_trust = (
        0.35 * _scale(g("p2p_unique_counterparties"), 1, 15)
        + 0.30 * _scale(g("counterparty_concentration_hhi"), 0.1, 0.8, invert=True)
        + 0.20 * _clip01(g("committee_participation"))
        + 0.15 * _scale(g("sim_tenure_months"), 0, 72)
    )

    return {
        "payment_discipline": int(round(_clip01(payment_discipline) * 100)),
        "cashflow_stability": int(round(_clip01(cashflow_stability) * 100)),
        "transaction_activity": int(round(_clip01(transaction_activity) * 100)),
        "savings_behavior": int(round(_clip01(savings_behavior) * 100)),
        "business_maturity": int(round(_clip01(business_maturity) * 100)),
        "network_trust": int(round(_clip01(network_trust) * 100)),
    }


# Portfolio-median radar polygon, for the dashed reference shape on BehaviorRadar.
PORTFOLIO_MEDIAN_RADAR: dict[str, int] = behavioral_metrics(dict(POPULATION_MEDIANS))
