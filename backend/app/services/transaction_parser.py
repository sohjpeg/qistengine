"""Wallet transaction-log parser.

Accepts CSV or JSON exports from JazzCash, EasyPaisa, SadaPay, NayaPay or a
hand-kept Digital Khata ledger. Column names differ across all of them, so the
mapping is tolerant. Output is a canonical ledger plus the transaction-behaviour
and cashflow feature block.
"""
from __future__ import annotations

import io
import json
import math
import re
from collections import defaultdict
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from dateutil import parser as dateparser

from app.config import settings

COLUMN_ALIASES: dict[str, list[str]] = {
    "date": ["date", "txn_date", "transaction_date", "tarikh", "datetime", "time"],
    "amount": ["amount", "txn_amount", "rakam", "value", "amt"],
    "direction": ["direction", "type", "dr_cr", "debit/credit", "debit_credit", "cr_dr", "flow"],
    "counterparty": ["counterparty", "description", "tafseel", "detail", "details", "narration", "party", "remarks", "note", "to", "from"],
    "balance": ["balance", "closing_balance", "running_balance", "bal", "available_balance"],
    "channel": ["channel", "mode", "txn_type", "method", "medium"],
}

# Urdu + English keyword -> category
_KEYWORDS: list[tuple[str, str]] = [
    (r"\b(bijli|electric|k-?electric|lesco|fesco|iesco|mepco|pesco|qesco|hesco|gepco|sui|gas|ssgc|sngpl|ptcl|water|bill)\b", "OUTFLOW_UTILITY"),
    (r"\b(topup|top-?up|load|easyload|recharge|balance|mobile|jazz|zong|ufone|telenor)\b", "OUTFLOW_TOPUP"),
    (r"\b(committee|\bbc\b|rosca|kameti|bisi)\b", "COMMITTEE"),
    (r"\b(rashan|rashon|grocery|kiryana|atta|flour|sabzi|ration|kharcha|kharch)\b", "OUTFLOW_ESSENTIAL"),
    (r"\b(salary|tankhwah|wages|ujrat|payroll)\b", "INFLOW_SALARY"),
    (r"\b(qr|merchant|shop|dukan|store|pos|sale|sales|customer)\b", "INFLOW_MERCHANT"),
    (r"\b(restaurant|cafe|shopping|movie|game|entertainment|clothes|fashion)\b", "OUTFLOW_DISCRETIONARY"),
]
_P2P_HINT = re.compile(r"\b(transfer|iban|account|wallet|send|receive|p2p|person|cnic)\b", re.I)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(s).strip().lower())


def _load_rows(filename: str, data: bytes) -> list[dict[str, Any]]:
    if len(data) > settings.max_upload_bytes:
        raise ValueError(f"File exceeds {settings.max_upload_mb} MB limit")
    text = data.decode("utf-8", errors="replace")
    name_l = filename.lower()
    if name_l.endswith(".json") or text.lstrip().startswith(("[", "{")):
        obj = json.loads(text)
        if isinstance(obj, dict):
            for key in ("transactions", "data", "rows", "ledger", "records"):
                if key in obj and isinstance(obj[key], list):
                    obj = obj[key]
                    break
        if not isinstance(obj, list):
            raise ValueError("JSON must be a list of transactions or an object containing one")
        return [dict(r) for r in obj]
    df = pd.read_csv(io.StringIO(text))
    return df.to_dict(orient="records")


def _resolve_columns(sample_keys: list[str]) -> dict[str, str | None]:
    normed = {_norm(k): k for k in sample_keys}
    resolved: dict[str, str | None] = {}
    for canon, aliases in COLUMN_ALIASES.items():
        found = None
        for alias in aliases:
            if _norm(alias) in normed:
                found = normed[_norm(alias)]
                break
        if not found:  # loose bidirectional contains match
            for nk, orig in normed.items():
                if any(_norm(a) in nk or nk in _norm(a) for a in aliases):
                    found = orig
                    break
        resolved[canon] = found
    return resolved


def _to_float(v: Any) -> float | None:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    s = re.sub(r"[^0-9.\-]", "", str(v))
    if s in ("", "-", "."):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _direction(row_dir: Any, amount: float | None) -> str:
    if row_dir is not None and str(row_dir).strip():
        d = str(row_dir).strip().lower()
        if d in ("cr", "credit", "c", "in", "inflow", "deposit", "+"):
            return "credit"
        if d in ("dr", "debit", "d", "out", "outflow", "withdrawal", "-"):
            return "debit"
    if amount is not None:
        return "credit" if amount >= 0 else "debit"
    return "debit"


def _classify(counterparty: str, channel: str | None, direction: str) -> str:
    hay = f"{counterparty} {channel or ''}".lower()
    for pat, cat in _KEYWORDS:
        if re.search(pat, hay):
            if cat.startswith("INFLOW") and direction == "debit":
                continue
            if cat.startswith("OUTFLOW") and direction == "credit":
                continue
            return cat
    if _P2P_HINT.search(hay):
        return "INFLOW_P2P" if direction == "credit" else "OUTFLOW_P2P"
    return "INFLOW_MERCHANT" if direction == "credit" else "OUTFLOW_DISCRETIONARY"


def _month_key(d: datetime) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def parse_transactions(filename: str, data: bytes) -> dict[str, Any]:
    rows = _load_rows(filename, data)
    if not rows:
        raise ValueError("No transactions found in file")

    cols = _resolve_columns(list(rows[0].keys()))
    if not cols["date"] or not cols["amount"]:
        raise ValueError(
            "Could not find a date and an amount column. Accepted date headers: "
            + ", ".join(COLUMN_ALIASES["date"])
        )

    canonical: list[dict[str, Any]] = []
    for r in rows:
        raw_amt = _to_float(r.get(cols["amount"]))
        if raw_amt is None:
            continue
        try:
            d = dateparser.parse(str(r.get(cols["date"])), dayfirst=True)
        except (ValueError, OverflowError, TypeError):
            continue
        direction = _direction(r.get(cols["direction"]) if cols["direction"] else None, raw_amt)
        amount = abs(raw_amt)
        counterparty = str(r.get(cols["counterparty"], "") if cols["counterparty"] else "").strip() or "unknown"
        channel = str(r.get(cols["channel"], "") if cols["channel"] else "").strip() or None
        balance = _to_float(r.get(cols["balance"])) if cols["balance"] else None
        category = _classify(counterparty, channel, direction)
        canonical.append(
            {
                "date": d.date().isoformat(),
                "_dt": d,
                "amount": round(amount, 2),
                "direction": direction,
                "counterparty": counterparty[:80],
                "balance": balance,
                "channel": channel,
                "category": category,
            }
        )

    if not canonical:
        raise ValueError("No parseable transaction rows after normalisation")

    canonical.sort(key=lambda x: x["_dt"])
    features, monthly = _derive(canonical)
    for c in canonical:
        c.pop("_dt", None)

    return {
        "filename": filename,
        "row_count": len(canonical),
        "months_observed": len(monthly),
        "transactions": canonical,
        "derived_features": features,
        "monthly_series": monthly,
    }


def _derive(txns: list[dict[str, Any]]) -> tuple[dict[str, float], list[dict[str, Any]]]:
    by_month: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    counterparty_vol: dict[str, float] = defaultdict(float)
    p2p_counterparties: set[str] = set()
    topup_dates: list[datetime] = []
    balances: list[float] = []
    n_p2p = 0
    n_committee = 0
    essential_out = 0.0
    total_out = 0.0
    total_in = 0.0
    merchant_in = 0.0

    for t in txns:
        mk = _month_key(t["_dt"])
        m = by_month[mk]
        m["count"] += 1
        if t["balance"] is not None:
            balances.append(t["balance"])
            m["min_balance"] = min(m.get("min_balance", t["balance"]), t["balance"])
        if t["direction"] == "credit":
            m["inflow"] += t["amount"]
            total_in += t["amount"]
            if t["category"] == "INFLOW_MERCHANT":
                merchant_in += t["amount"]
            if t["category"] == "INFLOW_P2P":
                n_p2p += 1
                p2p_counterparties.add(t["counterparty"])
        else:
            m["outflow"] += t["amount"]
            total_out += t["amount"]
            counterparty_vol[t["counterparty"]] += t["amount"]
            if t["category"] in ("OUTFLOW_UTILITY", "OUTFLOW_ESSENTIAL"):
                essential_out += t["amount"]
            if t["category"] == "OUTFLOW_P2P":
                n_p2p += 1
                p2p_counterparties.add(t["counterparty"])
            if t["category"] == "OUTFLOW_TOPUP":
                topup_dates.append(t["_dt"])
            if t["category"] == "COMMITTEE":
                n_committee += 1
        if t["category"] == "OUTFLOW_UTILITY":
            m["utility_paid"] = 1.0

    months = sorted(by_month)
    n_months = max(len(months), 1)
    inflows = np.array([by_month[mk]["inflow"] for mk in months], dtype=float)
    outflows = np.array([by_month[mk]["outflow"] for mk in months], dtype=float)
    nets = inflows - outflows
    mean_inflow = float(inflows.mean()) if len(inflows) else 0.0
    mean_outflow = float(outflows.mean()) if len(outflows) else 0.0

    cashflow_volatility = float(np.std(nets) / mean_inflow) if mean_inflow > 0 else 0.5
    if len(inflows) >= 2:
        x = np.arange(len(inflows), dtype=float)
        slope = float(np.polyfit(x, inflows, 1)[0])
        income_trend_slope = slope / mean_inflow if mean_inflow > 0 else 0.0
    else:
        income_trend_slope = 0.0

    total_cp_vol = sum(counterparty_vol.values()) or 1.0
    hhi = float(sum((v / total_cp_vol) ** 2 for v in counterparty_vol.values()))

    if len(topup_dates) >= 2:
        gaps = np.diff(sorted(datetime.timestamp(d) for d in topup_dates)) / 86400.0
        topup_reg = float(max(0.0, 1.0 - (np.std(gaps) / (np.mean(gaps) + 1e-6))))
    else:
        topup_reg = 0.3

    min_balances = [by_month[mk].get("min_balance", 0.0) for mk in months if "min_balance" in by_month[mk]]
    zero_days_ratio = (
        float(np.mean([1.0 if b < 200 else 0.0 for b in balances])) if balances else 0.2
    )
    balance_floor_ratio = (
        float(np.percentile(balances, 10) / mean_inflow) if balances and mean_inflow > 0 else 0.05
    )

    features = {
        "monthly_inflow_pkr": round(mean_inflow, 2),
        "monthly_outflow_pkr": round(mean_outflow, 2),
        "net_cashflow_ratio": round(float(nets.mean() / mean_inflow), 4) if mean_inflow > 0 else 0.0,
        "cashflow_volatility": round(min(cashflow_volatility, 1.4), 4),
        "income_trend_slope": round(float(np.clip(income_trend_slope, -0.4, 0.4)), 4),
        "zero_balance_days_ratio": round(min(zero_days_ratio, 1.0), 4),
        "balance_floor_ratio": round(float(np.clip(balance_floor_ratio, 0.0, 0.7)), 4),
        "p2p_velocity": round(n_p2p / n_months, 3),
        "p2p_unique_counterparties": round(len(p2p_counterparties) / n_months, 3),
        "counterparty_concentration_hhi": round(min(max(hhi, 0.03), 0.98), 4),
        "merchant_inflow_share": round(merchant_in / total_in, 4) if total_in > 0 else 0.0,
        "txn_frequency_monthly": round(len(txns) / n_months, 2),
        "mobile_topup_regularity": round(min(max(topup_reg, 0.0), 1.0), 4),
        "expense_to_income_ratio": round(essential_out / total_in, 4) if total_in > 0 else 0.8,
        "savings_rate": round(float(np.clip((np.mean(min_balances) / mean_inflow) if (min_balances and mean_inflow > 0) else 0.08, 0.0, 0.7)), 4),
        "committee_participation": 1.0 if n_committee > 0 else 0.0,
    }

    monthly_series = [
        {
            "month": mk,
            "inflow_pkr": round(by_month[mk]["inflow"], 0),
            "outflow_pkr": round(by_month[mk]["outflow"], 0),
            "utility_paid_on_time": bool(by_month[mk].get("utility_paid", 0.0)),
        }
        for mk in months
    ]
    return features, monthly_series
