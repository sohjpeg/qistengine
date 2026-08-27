"""End-to-end scoring pipeline: raw signals -> ScoreResponse payload.

Shared by POST /api/v1/score and POST /api/v1/applications so both paths produce
byte-identical results for the same input.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

import numpy as np

from app.ml.registry import registry
from app.schemas import DISCLAIMER
from app.services import qist_limit as qist
from app.services.explainer import explain
from app.services.feature_engineering import (
    FEATURE_ORDER,
    POPULATION_MEDIANS,
    PORTFOLIO_MEDIAN_RADAR,
    behavioral_metrics,
    build_feature_vector,
    confidence_from_gaps,
    detect_data_gaps,
)
from app.services.scorecard import pd_to_score, score_to_band

_MONTHS = 12
_SEASONAL_INFLOW = {  # month index 0..11 starting 11 months ago; Ramzan/Eid bumps
    "ramzan_eid": 1.35,
    "monsoon": 0.8,
}


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _recent_months(n: int = _MONTHS) -> list[str]:
    now = datetime.now(timezone.utc)
    ym = now.year * 12 + (now.month - 1)
    out = []
    for k in range(n, 0, -1):
        m = ym - k
        out.append(f"{m // 12:04d}-{m % 12 + 1:02d}")
    return out


def synth_monthly_series(raw: dict[str, Any], archetype: str | None) -> list[dict[str, Any]]:
    """Deterministically reconstruct a 12-month inflow/outflow series from the
    aggregate features, with plausible seasonality. Used when the caller did not
    upload a transaction log."""
    inflow = float(raw.get("monthly_inflow_pkr") or POPULATION_MEDIANS["monthly_inflow_pkr"])
    outflow = float(raw.get("monthly_outflow_pkr") or POPULATION_MEDIANS["monthly_outflow_pkr"])
    vol = float(raw.get("cashflow_volatility") or POPULATION_MEDIANS["cashflow_volatility"])
    trend = float(raw.get("income_trend_slope") or 0.0)
    on_time = float(raw.get("utility_on_time_ratio") or POPULATION_MEDIANS["utility_on_time_ratio"])

    seed_src = f"{archetype}|{inflow:.0f}|{outflow:.0f}|{vol:.3f}".encode()
    rng = np.random.default_rng(int.from_bytes(hashlib.sha256(seed_src).digest()[:8], "big"))

    months = _recent_months()
    series = []
    for i, ym in enumerate(months):
        month_num = int(ym.split("-")[1])
        seasonal = 1.0
        if month_num in (3, 4, 5):  # rough Ramzan / Eid window
            seasonal *= 1.18 if archetype == "kiryana_merchant" else 1.06
        if month_num in (7, 8):  # monsoon
            seasonal *= 0.82 if archetype == "daily_wage_worker" else 0.95
        drift = 1.0 + trend * (i - _MONTHS / 2) / _MONTHS
        shock = float(rng.normal(1.0, min(0.35, max(0.03, vol * 0.6))))
        m_inflow = max(0.0, inflow * seasonal * drift * shock)
        m_outflow = max(0.0, outflow * (0.9 + 0.2 * float(rng.random())) * (0.5 + 0.5 * seasonal))
        paid_on_time = float(rng.random()) <= on_time
        series.append(
            {
                "month": ym,
                "inflow_pkr": round(m_inflow, 0),
                "outflow_pkr": round(m_outflow, 0),
                "utility_paid_on_time": bool(paid_on_time),
            }
        )
    return series


def merge_raw_signals(
    features: dict[str, Any] | None,
    bill_fields: dict[str, Any] | None,
    transaction_aggregates: dict[str, Any] | None,
) -> dict[str, Any]:
    """Combine the caller's inputs into a single raw-feature dict keyed by
    FEATURE_ORDER names. Values not provided are left absent (imputed later)."""
    raw: dict[str, Any] = {}
    for src in (features, transaction_aggregates, bill_fields):
        if not src:
            continue
        for k, v in src.items():
            if k in FEATURE_ORDER and v is not None:
                raw[k] = v
    return raw


def run_scoring(
    raw_signals: dict[str, Any],
    *,
    applicant_id: str | None = None,
    archetype_hint: str | None = None,
    monthly_series: list[dict[str, Any]] | None = None,
    tenor_months: int | None = None,
) -> dict[str, Any]:
    registry.ensure()
    if not registry.loaded:
        raise RuntimeError(
            registry.error
            or "Model artifacts not loaded. Run: python scripts/train_model.py"
        )

    gaps = detect_data_gaps(raw_signals)
    vec = build_feature_vector(raw_signals)

    shap_vals = registry.shap_values(vec)
    # Score from the uncalibrated model margin so the reason-code ledger sums to
    # the score exactly (score is affine in log-odds, SHAP is additive in log-odds).
    margin = registry.score_margin(shap_vals)
    pd_for_score = 1.0 / (1.0 + np.exp(-margin))
    score = pd_to_score(pd_for_score)
    band = score_to_band(score)
    # Calibrated probability for display + the Qist Limit affordability maths.
    # Isotonic calibration can pin extreme rows to exactly 0 or 1; clamp to a
    # sane display range so the UI never shows "PD 0.0%".
    pd_hat = min(0.98, max(0.002, registry.predict_pd(vec)))

    # complete raw dict (imputed) for templates / limit / radar
    complete_raw = {name: float(vec[i]) for i, name in enumerate(FEATURE_ORDER)}
    for k, v in raw_signals.items():
        if k in FEATURE_ORDER and v is not None:
            complete_raw[k] = float(v)

    expl = explain(shap_vals, complete_raw, registry.expected_value, top_k=4)
    limit = qist.compute_qist_limit(complete_raw, band.key, tenor_override=tenor_months)
    radar = behavioral_metrics(complete_raw)

    if not monthly_series:
        monthly_series = synth_monthly_series(complete_raw, archetype_hint)

    confidence = confidence_from_gaps(gaps, complete_raw.get("utility_months_observed", 12.0))

    return {
        "application_id": applicant_id,
        "score": score,
        "probability_of_default": round(float(pd_hat), 4),
        "risk_band": band.key,
        "band_label": band.label,
        "confidence": confidence,
        "qist_limit": limit,
        "reason_codes": expl["reason_codes"],
        "ledger_lines": expl["all_contributions"],
        "base_contribution": expl["base_contribution"],
        "adverse_action_codes": expl["adverse_action_codes"] if band.key != "LOW" else [],
        "behavioral_metrics": radar,
        "portfolio_median_metrics": PORTFOLIO_MEDIAN_RADAR,
        "monthly_series": monthly_series,
        "data_gaps": gaps,
        "model_version": registry.version,
        "scored_at": _iso_now(),
        "disclaimer": DISCLAIMER,
        "_features_used": complete_raw,
    }
