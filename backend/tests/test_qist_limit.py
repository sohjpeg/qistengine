"""Safe Qist Limit invariants."""
from __future__ import annotations

import pytest

from app.services.qist_limit import (
    MAX_INSTALLMENT,
    MIN_INSTALLMENT,
    compute_qist_limit,
)

BASE = {
    "monthly_inflow_pkr": 90000,
    "monthly_outflow_pkr": 60000,
    "cashflow_volatility": 0.25,
    "utility_months_observed": 12,
    "utility_on_time_ratio": 0.9,
}


def test_installment_never_negative_and_rounds_to_500():
    for band in ("LOW", "MEDIUM", "HIGH", "VERY_HIGH"):
        r = compute_qist_limit(BASE, band)
        assert r["safe_installment_pkr"] >= 0
        assert r["safe_installment_pkr"] % 500 == 0
        assert r["safe_installment_pkr"] <= MAX_INSTALLMENT


def test_principal_rounds_to_1000_and_is_consistent():
    r = compute_qist_limit(BASE, "LOW")
    assert r["eligible"] is True
    assert r["principal_pkr"] % 1000 == 0
    # total repayable == installment * tenor
    assert r["total_repayable_pkr"] == r["safe_installment_pkr"] * r["tenor_months"]
    # principal is discounted by the flat markup
    assert r["principal_pkr"] <= r["total_repayable_pkr"]


def test_low_disposable_income_is_ineligible():
    poor = dict(BASE, monthly_inflow_pkr=20000, monthly_outflow_pkr=19000)
    r = compute_qist_limit(poor, "HIGH")
    assert r["eligible"] is False
    assert r["reason"] == "INSUFFICIENT_DISPOSABLE_INCOME"
    assert r["safe_installment_pkr"] == 0
    assert r["principal_pkr"] == 0


def test_dsr_cap_tightens_with_risk():
    caps = [compute_qist_limit(BASE, b)["breakdown"]["dsr_cap"] for b in ("LOW", "MEDIUM", "HIGH", "VERY_HIGH")]
    assert caps == sorted(caps, reverse=True)


def test_volatility_haircut_clamped():
    calm = compute_qist_limit(dict(BASE, cashflow_volatility=0.0), "LOW")["breakdown"]["volatility_haircut"]
    wild = compute_qist_limit(dict(BASE, cashflow_volatility=2.0), "LOW")["breakdown"]["volatility_haircut"]
    assert calm == 1.0
    assert wild == 0.45


def test_depth_confidence_clamped():
    thin = compute_qist_limit(dict(BASE, utility_months_observed=0), "LOW")["breakdown"]["depth_confidence"]
    long = compute_qist_limit(dict(BASE, utility_months_observed=24), "LOW")["breakdown"]["depth_confidence"]
    assert thin == 0.5
    assert long == 1.0


def test_tenor_override_only_accepts_valid_values():
    r = compute_qist_limit(BASE, "LOW", tenor_override=6)
    assert r["tenor_months"] == 6
    r2 = compute_qist_limit(BASE, "LOW", tenor_override=7)
    assert r2["tenor_months"] == 12  # falls back to band default


def test_higher_on_time_ratio_gives_a_bonus():
    low = compute_qist_limit(dict(BASE, utility_on_time_ratio=0.0), "LOW")["breakdown"]["consistency_bonus"]
    high = compute_qist_limit(dict(BASE, utility_on_time_ratio=1.0), "LOW")["breakdown"]["consistency_bonus"]
    assert high > low
    assert low == 1.0
