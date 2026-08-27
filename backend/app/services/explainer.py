"""SHAP -> score-points explanation with exact additivity.

Model margin (log-odds of default):  f(x) = expected_value + sum_j shap_j
Score:                               score = OFFSET + FACTOR * ln((1-pd)/pd)
                                           = OFFSET - FACTOR * f(x)
                                           = [OFFSET - FACTOR * expected_value]
                                             + sum_j (-FACTOR * shap_j)

So  base_contribution = OFFSET - FACTOR * expected_value
and points_j          = -FACTOR * shap_j
and  base_contribution + sum_j points_j == raw_score   (exact, pre-rounding/clip)

test_scorecard.py / test_features.py assert this holds within 2 points of the
displayed (rounded, clipped) score.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from app.services.feature_engineering import FEATURE_CATEGORY, FEATURE_ORDER
from app.services.scorecard import FACTOR, OFFSET

ADVERSE_ACTION_CODES: dict[str, str] = {
    "utility_on_time_ratio": "AA01-UTILITY-PAYMENT-HISTORY",
    "utility_avg_days_late": "AA02-CHRONIC-LATE-PAYMENT",
    "utility_bill_volatility": "AA03-UNSTABLE-BILLED-USAGE",
    "utility_months_observed": "AA04-THIN-UTILITY-FILE",
    "utility_disconnection_events": "AA05-SERVICE-DISCONNECTION",
    "monthly_inflow_pkr": "AA06-LOW-RECORDED-INCOME",
    "monthly_outflow_pkr": "AA07-HIGH-RECORDED-OUTFLOW",
    "net_cashflow_ratio": "AA08-NEGATIVE-NET-CASHFLOW",
    "cashflow_volatility": "AA09-VOLATILE-CASHFLOW",
    "income_trend_slope": "AA10-DECLINING-INCOME-TREND",
    "zero_balance_days_ratio": "AA11-FREQUENT-ZERO-BALANCE",
    "balance_floor_ratio": "AA12-NO-CASH-BUFFER",
    "p2p_velocity": "AA13-ATYPICAL-TRANSFER-VELOCITY",
    "p2p_unique_counterparties": "AA14-NARROW-TRANSFER-NETWORK",
    "counterparty_concentration_hhi": "AA15-CONCENTRATED-COUNTERPARTIES",
    "merchant_inflow_share": "AA16-LOW-MERCHANT-RECEIPTS",
    "txn_frequency_monthly": "AA17-LOW-TRANSACTION-ACTIVITY",
    "mobile_topup_regularity": "AA18-IRREGULAR-TOPUP-PATTERN",
    "expense_to_income_ratio": "AA19-HIGH-EXPENSE-BURDEN",
    "savings_rate": "AA20-LOW-SAVINGS-RATE",
    "committee_participation": "AA21-NO-COMMITTEE-SAVINGS",
    "wallet_tenure_months": "AA22-SHORT-WALLET-TENURE",
    "business_age_months": "AA23-NEW-BUSINESS",
    "dependents_count": "AA24-HIGH-DEPENDENT-LOAD",
    "has_fixed_premises": "AA25-NO-FIXED-PREMISES",
    "sim_tenure_months": "AA26-SHORT-SIM-TENURE",
}


def _ctx(raw: dict[str, Any]) -> dict[str, Any]:
    """Derived display values interpolated into templates."""
    g = lambda k, d=0.0: float(raw.get(k, d) if raw.get(k) is not None else d)  # noqa: E731
    months = max(1.0, g("utility_months_observed", 12.0))
    on_time_n = int(round(g("utility_on_time_ratio", 0.0) * months))
    return {
        "months_total": int(round(months)),
        "on_time_n": on_time_n,
        "missed_n": max(0, int(round(months)) - on_time_n),
        "days_late": int(round(g("utility_avg_days_late"))),
        "bill_cv_pct": round(g("utility_bill_volatility") * 100, 1),
        "cv_pct": round(g("cashflow_volatility") * 100, 1),
        "disconnections": int(round(g("utility_disconnection_events"))),
        "inflow": int(round(g("monthly_inflow_pkr"))),
        "outflow": int(round(g("monthly_outflow_pkr"))),
        "net_pct": round(g("net_cashflow_ratio") * 100, 1),
        "trend_pct": round(g("income_trend_slope") * 100, 1),
        "zero_days": int(round(g("zero_balance_days_ratio") * 30)),
        "buffer_pct": round(g("balance_floor_ratio") * 100, 1),
        "p2p_v": round(g("p2p_velocity"), 1),
        "p2p_n": int(round(g("p2p_unique_counterparties"))),
        "hhi": round(g("counterparty_concentration_hhi"), 2),
        "merchant_pct": round(g("merchant_inflow_share") * 100, 1),
        "txn_n": int(round(g("txn_frequency_monthly"))),
        "topup_reg_pct": round(g("mobile_topup_regularity") * 100, 1),
        "expense_pct": round(g("expense_to_income_ratio") * 100, 1),
        "savings_pct": round(g("savings_rate") * 100, 1),
        "wallet_m": int(round(g("wallet_tenure_months"))),
        "business_m": int(round(g("business_age_months"))),
        "dependents": int(round(g("dependents_count"))),
        "sim_m": int(round(g("sim_tenure_months"))),
    }


# (positive_en, negative_en, positive_ur, negative_ur). "{pts}" and derived keys interpolate.
TEMPLATES: dict[str, tuple[str, str, str, str]] = {
    "utility_on_time_ratio": (
        "{pts} pts — Paid {on_time_n} of {months_total} electricity bills on time",
        "{pts} pts — Missed {missed_n} bill due dates in the last year",
        "{pts} پوائنٹس — {months_total} میں سے {on_time_n} بجلی کے بل وقت پر ادا کیے",
        "{pts} پوائنٹس — پچھلے سال {missed_n} بلوں کی تاریخ گزر گئی",
    ),
    "utility_avg_days_late": (
        "{pts} pts — Bills cleared close to the due date",
        "{pts} pts — Bills paid on average {days_late} days late",
        "{pts} پوائنٹس — بل آخری تاریخ کے قریب ادا کیے گئے",
        "{pts} پوائنٹس — بل اوسطاً {days_late} دن تاخیر سے ادا کیے",
    ),
    "utility_bill_volatility": (
        "{pts} pts — Electricity usage is steady month to month",
        "{pts} pts — Billed usage swings by {bill_cv_pct}% between months",
        "{pts} پوائنٹس — بجلی کا استعمال ہر مہینے مستحکم ہے",
        "{pts} پوائنٹس — بل کی رقم مہینوں کے درمیان {bill_cv_pct}% بدلتی ہے",
    ),
    "utility_months_observed": (
        "{pts} pts — {months_total} months of billing history on file",
        "{pts} pts — Only {months_total} months of billing history",
        "{pts} پوائنٹس — {months_total} مہینوں کی بلنگ ہسٹری موجود",
        "{pts} پوائنٹس — صرف {months_total} مہینوں کی بلنگ ہسٹری",
    ),
    "utility_disconnection_events": (
        "{pts} pts — No electricity disconnections on record",
        "{pts} pts — {disconnections} service disconnection(s) in the last year",
        "{pts} پوائنٹس — بجلی کا کوئی کنیکشن منقطع نہیں ہوا",
        "{pts} پوائنٹس — پچھلے سال {disconnections} بار کنیکشن کٹا",
    ),
    "monthly_inflow_pkr": (
        "{pts} pts — Recorded monthly inflow of Rs {inflow}",
        "{pts} pts — Recorded monthly inflow is only Rs {inflow}",
        "{pts} پوائنٹس — ماہانہ آمدنی Rs {inflow} ریکارڈ ہوئی",
        "{pts} پوائنٹس — ماہانہ آمدنی صرف Rs {inflow} ہے",
    ),
    "monthly_outflow_pkr": (
        "{pts} pts — Outflow well contained at Rs {outflow} a month",
        "{pts} pts — Monthly outflow of Rs {outflow} leaves little slack",
        "{pts} پوائنٹس — ماہانہ اخراجات Rs {outflow} تک محدود",
        "{pts} پوائنٹس — ماہانہ Rs {outflow} اخراجات سے گنجائش کم رہتی ہے",
    ),
    "net_cashflow_ratio": (
        "{pts} pts — Keeps {net_pct}% of inflow after outgoings",
        "{pts} pts — Net cash flow is thin at {net_pct}% of inflow",
        "{pts} پوائنٹس — اخراجات کے بعد آمدنی کا {net_pct}% بچتا ہے",
        "{pts} پوائنٹس — خالص بچت صرف {net_pct}% ہے",
    ),
    "cashflow_volatility": (
        "{pts} pts — Steady month-to-month cash flow",
        "{pts} pts — Monthly income swings by {cv_pct}%",
        "{pts} پوائنٹس — ماہانہ نقد بہاؤ مستحکم ہے",
        "{pts} پوائنٹس — ماہانہ آمدنی {cv_pct}% تک کم زیادہ ہوتی ہے",
    ),
    "income_trend_slope": (
        "{pts} pts — Income trending up {trend_pct}% over six months",
        "{pts} pts — Income trending down {trend_pct}% over six months",
        "{pts} پوائنٹس — چھ مہینوں میں آمدنی {trend_pct}% بڑھی",
        "{pts} پوائنٹس — چھ مہینوں میں آمدنی {trend_pct}% گری",
    ),
    "zero_balance_days_ratio": (
        "{pts} pts — Wallet rarely runs empty",
        "{pts} pts — Wallet balance drops near zero {zero_days} days a month",
        "{pts} پوائنٹس — والٹ شاذ ہی خالی ہوتا ہے",
        "{pts} پوائنٹس — والٹ کا بیلنس مہینے میں {zero_days} دن صفر کے قریب ہوتا ہے",
    ),
    "balance_floor_ratio": (
        "{pts} pts — Maintains a cash buffer between earnings",
        "{pts} pts — Almost no cash buffer between earnings ({buffer_pct}%)",
        "{pts} پوائنٹس — آمدنی کے درمیان نقد ذخیرہ رکھتا ہے",
        "{pts} پوائنٹس — آمدنی کے درمیان نقد ذخیرہ تقریباً نہیں ({buffer_pct}%)",
    ),
    "p2p_velocity": (
        "{pts} pts — Healthy transfer activity with {p2p_n} regular contacts",
        "{pts} pts — Transfer pattern is unusually concentrated",
        "{pts} پوائنٹس — {p2p_n} باقاعدہ رابطوں کے ساتھ مناسب لین دین",
        "{pts} پوائنٹس — رقم کی منتقلی کا طریقہ غیر معمولی طور پر محدود",
    ),
    "p2p_unique_counterparties": (
        "{pts} pts — Transfers spread across {p2p_n} counterparties a month",
        "{pts} pts — Transfers reach only {p2p_n} counterparties a month",
        "{pts} پوائنٹس — ماہانہ {p2p_n} فریقوں کے ساتھ لین دین",
        "{pts} پوائنٹس — ماہانہ صرف {p2p_n} فریقوں تک محدود",
    ),
    "counterparty_concentration_hhi": (
        "{pts} pts — Transfer counterparties are well diversified",
        "{pts} pts — Transfers concentrated on very few counterparties (HHI {hhi})",
        "{pts} پوائنٹس — لین دین متنوع فریقوں میں تقسیم ہے",
        "{pts} پوائنٹس — لین دین چند فریقوں پر مرکوز (HHI {hhi})",
    ),
    "merchant_inflow_share": (
        "{pts} pts — {merchant_pct}% of inflow is merchant/QR receipts",
        "{pts} pts — Only {merchant_pct}% of inflow is merchant/QR receipts",
        "{pts} پوائنٹس — آمدنی کا {merchant_pct}% تاجرانہ/QR وصولیاں",
        "{pts} پوائنٹس — آمدنی کا صرف {merchant_pct}% تاجرانہ/QR وصولیاں",
    ),
    "txn_frequency_monthly": (
        "{pts} pts — Active wallet with {txn_n} transactions a month",
        "{pts} pts — Low wallet activity at {txn_n} transactions a month",
        "{pts} پوائنٹس — فعال والٹ، ماہانہ {txn_n} لین دین",
        "{pts} پوائنٹس — کم والٹ سرگرمی، ماہانہ {txn_n} لین دین",
    ),
    "mobile_topup_regularity": (
        "{pts} pts — Tops up mobile balance on a regular cycle",
        "{pts} pts — Mobile top-ups are irregular",
        "{pts} پوائنٹس — موبائل بیلنس باقاعدگی سے ڈلتا ہے",
        "{pts} پوائنٹس — موبائل ڈلوانے کا طریقہ غیر منظم",
    ),
    "expense_to_income_ratio": (
        "{pts} pts — Spends {expense_pct}% of income, leaving room to repay",
        "{pts} pts — Expenses consume {expense_pct}% of monthly income",
        "{pts} پوائنٹس — آمدنی کا {expense_pct}% خرچ، واپسی کی گنجائش",
        "{pts} پوائنٹس — اخراجات ماہانہ آمدنی کا {expense_pct}% لی لیتے ہیں",
    ),
    "savings_rate": (
        "{pts} pts — Holds about {savings_pct}% of inflow as month-end balance",
        "{pts} pts — Month-end balance is only {savings_pct}% of inflow",
        "{pts} پوائنٹس — مہینے کے آخر میں آمدنی کا تقریباً {savings_pct}% بچتا ہے",
        "{pts} پوائنٹس — مہینے کے آخر کا بیلنس آمدنی کا صرف {savings_pct}%",
    ),
    "committee_participation": (
        "{pts} pts — Regular committee (BC) contributions show savings discipline",
        "{pts} pts — No committee (BC) savings detected in the ledger",
        "{pts} پوائنٹس — باقاعدہ کمیٹی (BC) ادائیگی بچت کی عادت ظاہر کرتی ہے",
        "{pts} پوائنٹس — لیجر میں کوئی کمیٹی (BC) بچت نہیں ملی",
    ),
    "wallet_tenure_months": (
        "{pts} pts — Wallet in use for {wallet_m} months",
        "{pts} pts — Wallet opened only {wallet_m} months ago",
        "{pts} پوائنٹس — والٹ {wallet_m} مہینے سے زیر استعمال",
        "{pts} پوائنٹس — والٹ صرف {wallet_m} مہینے پہلے کھولا",
    ),
    "business_age_months": (
        "{pts} pts — Business running for {business_m} months",
        "{pts} pts — Business is new at {business_m} months",
        "{pts} پوائنٹس — کاروبار {business_m} مہینے سے چل رہا ہے",
        "{pts} پوائنٹس — کاروبار نیا ہے، صرف {business_m} مہینے",
    ),
    "dependents_count": (
        "{pts} pts — Manageable dependent load ({dependents})",
        "{pts} pts — High dependent load ({dependents} people)",
        "{pts} پوائنٹس — قابل انتظام کفالت ({dependents})",
        "{pts} پوائنٹس — زیادہ کفالت ({dependents} افراد)",
    ),
    "has_fixed_premises": (
        "{pts} pts — Operates from fixed business premises",
        "{pts} pts — No fixed business premises",
        "{pts} پوائنٹس — مقررہ کاروباری جگہ سے کام",
        "{pts} پوائنٹس — کوئی مقررہ کاروباری جگہ نہیں",
    ),
    "sim_tenure_months": (
        "{pts} pts — Same SIM for {sim_m} months",
        "{pts} pts — SIM registered only {sim_m} months ago",
        "{pts} پوائنٹس — وہی سم {sim_m} مہینے سے",
        "{pts} پوائنٹس — سم صرف {sim_m} مہینے پہلے رجسٹرڈ",
    ),
}

assert set(TEMPLATES) == set(FEATURE_ORDER), "Every feature needs a bilingual template."


def _fmt(tpl: str, pts_str: str, ctx: dict[str, Any]) -> str:
    return tpl.format(pts=pts_str, **ctx)


def base_contribution(expected_value: float) -> float:
    """Score points attributable to the model's prior (SHAP expected value)."""
    return OFFSET - FACTOR * float(expected_value)


def explain(
    shap_values: np.ndarray,
    raw_features: dict[str, Any],
    expected_value: float,
    top_k: int = 4,
) -> dict[str, Any]:
    """Convert per-feature SHAP values (log-odds of default) into scored reason codes.

    Returns dict with: reason_codes (top_k pos + top_k neg), all_contributions
    (every feature, for the ledger), adverse_action_codes, base_contribution.
    """
    shap_values = np.asarray(shap_values, dtype=np.float64).reshape(-1)
    if shap_values.shape[0] != len(FEATURE_ORDER):
        raise ValueError(f"Expected {len(FEATURE_ORDER)} SHAP values, got {shap_values.shape[0]}")

    ctx = _ctx(raw_features)
    points = -FACTOR * shap_values  # exact conversion

    contributions: list[dict[str, Any]] = []
    for i, feat in enumerate(FEATURE_ORDER):
        pts = float(points[i])
        pts_int = int(round(pts))
        if pts_int == 0:
            continue
        direction = "positive" if pts_int > 0 else "negative"
        pos_en, neg_en, pos_ur, neg_ur = TEMPLATES[feat]
        pts_str = f"+{pts_int}" if pts_int > 0 else f"{pts_int}"
        en = _fmt(pos_en if pts_int > 0 else neg_en, pts_str, ctx)
        ur = _fmt(pos_ur if pts_int > 0 else neg_ur, pts_str, ctx)
        contributions.append(
            {
                "feature": feat,
                "impact_points": pts_int,
                "impact_points_exact": round(pts, 4),
                "direction": direction,
                "label_en": en,
                "label_ur": ur,
                "category": FEATURE_CATEGORY[feat],
            }
        )

    contributions.sort(key=lambda c: c["impact_points_exact"], reverse=True)
    positives = [c for c in contributions if c["impact_points"] > 0][:top_k]
    negatives = [c for c in contributions if c["impact_points"] < 0]
    negatives_sorted = sorted(negatives, key=lambda c: c["impact_points_exact"])[:top_k]

    reason_codes = positives + negatives_sorted

    adverse = [
        ADVERSE_ACTION_CODES[c["feature"]]
        for c in sorted(negatives, key=lambda c: c["impact_points_exact"])[:3]
    ]

    return {
        "reason_codes": reason_codes,
        "all_contributions": contributions,
        "adverse_action_codes": adverse,
        "base_contribution": round(base_contribution(expected_value), 4),
    }
