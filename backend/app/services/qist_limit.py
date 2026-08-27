"""Safe Qist (installment) limit.

"Qist" is the installment, so the primary output is the affordable monthly
payment; principal follows from it. Every haircut is returned in the breakdown
so the UI can render a waterfall from raw disposable income down to the offer.
"""
from __future__ import annotations

import math
from typing import Any

DSR_CAP: dict[str, float] = {"LOW": 0.35, "MEDIUM": 0.25, "HIGH": 0.18, "VERY_HIGH": 0.10}
TENOR_MONTHS: dict[str, int] = {"LOW": 12, "MEDIUM": 9, "HIGH": 6, "VERY_HIGH": 3}
FLAT_MARKUP_PM: float = 0.015  # 1.5% per month, flat
MIN_INSTALLMENT: int = 2000
MAX_INSTALLMENT: int = 50_000


def _clip(x: float, lo: float, hi: float) -> float:
    return float(min(hi, max(lo, x)))


def compute_qist_limit(features: dict[str, Any], band_key: str, tenor_override: int | None = None) -> dict[str, Any]:
    inflow = float(features.get("monthly_inflow_pkr") or 0.0)
    outflow = float(features.get("monthly_outflow_pkr") or 0.0)
    cashflow_volatility = float(features.get("cashflow_volatility") or 0.0)
    months_observed = float(features.get("utility_months_observed") or 0.0)
    on_time = float(features.get("utility_on_time_ratio") or 0.0)

    disposable = inflow - outflow
    dsr_cap = DSR_CAP.get(band_key, 0.10)
    volatility_haircut = _clip(1.0 - cashflow_volatility, 0.45, 1.0)
    depth_confidence = _clip(months_observed / 12.0, 0.5, 1.0)
    consistency_bonus = 1.0 + 0.15 * _clip(on_time, 0.0, 1.0)

    safe = disposable * dsr_cap * volatility_haircut * depth_confidence * consistency_bonus
    safe_installment = math.floor(max(safe, 0.0) / 500.0) * 500
    safe_installment = int(_clip(safe_installment, 0, MAX_INSTALLMENT))

    breakdown = {
        "disposable_income_pkr": round(disposable, 2),
        "dsr_cap": round(dsr_cap, 4),
        "volatility_haircut": round(volatility_haircut, 4),
        "depth_confidence": round(depth_confidence, 4),
        "consistency_bonus": round(consistency_bonus, 4),
    }

    if safe_installment < MIN_INSTALLMENT:
        return {
            "eligible": False,
            "reason": "INSUFFICIENT_DISPOSABLE_INCOME",
            "safe_installment_pkr": 0,
            "principal_pkr": 0,
            "tenor_months": TENOR_MONTHS.get(band_key, 3),
            "flat_markup_monthly": FLAT_MARKUP_PM,
            "total_repayable_pkr": 0,
            "breakdown": breakdown,
        }

    tenor = tenor_override if tenor_override in (3, 6, 9, 12) else TENOR_MONTHS.get(band_key, 3)
    gross = safe_installment * tenor
    principal = gross / (1.0 + FLAT_MARKUP_PM * tenor)
    principal = int(math.floor(principal / 1000.0) * 1000)
    total_repayable = int(safe_installment * tenor)

    return {
        "eligible": True,
        "reason": None,
        "safe_installment_pkr": safe_installment,
        "principal_pkr": principal,
        "tenor_months": tenor,
        "flat_markup_monthly": FLAT_MARKUP_PM,
        "total_repayable_pkr": total_repayable,
        "breakdown": breakdown,
    }
