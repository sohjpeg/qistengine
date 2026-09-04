"""Wallet transaction-log parser.

Accepts **CSV, JSON, or PDF** exports from JazzCash, EasyPaisa, SadaPay, NayaPay,
Raast, a bank statement, or a hand-kept Digital Khata ledger. Real exports differ
wildly — different column names, preamble/marketing rows, split debit/credit
columns, amounts with "Rs"/commas/parentheses, "Cr"/"Dr" suffixes — so every
stage is deliberately tolerant. Output is one canonical ledger plus the
transaction-behaviour and cashflow feature block.

Anything it genuinely cannot read raises a clear error rather than guessing — a
wrong parse would feed the model garbage.
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
    "date": [
        "date", "txn_date", "transaction_date", "trans_date", "value_date",
        "posting_date", "tarikh", "datetime", "timestamp", "time", "day",
    ],
    "amount": [
        "amount", "txn_amount", "transaction_amount", "amt", "rakam", "value",
        "amount_pkr", "amount(pkr)", "amountrs",
    ],
    "debit": ["debit", "withdrawal", "withdrawals", "dr", "paid_out", "money_out", "outflow"],
    "credit": ["credit", "deposit", "deposits", "cr", "paid_in", "money_in", "inflow"],
    "direction": [
        "direction", "type", "txn_type", "transaction_type", "dr_cr", "drcr",
        "debit/credit", "debit_credit", "cr_dr", "flow", "nature",
    ],
    "counterparty": [
        "counterparty", "description", "desc", "details", "detail", "particulars",
        "narration", "transaction_details", "remarks", "remark", "note", "notes",
        "memo", "reference", "ref", "tafseel", "party", "to", "from", "merchant",
        "beneficiary", "payee", "sender",
    ],
    "balance": [
        "balance", "closing_balance", "running_balance", "available_balance",
        "bal", "balance_pkr", "ledger_balance",
    ],
    "channel": ["channel", "mode", "method", "medium", "instrument"],
}

# Urdu + English keyword -> category. Order matters (first match wins).
_KEYWORDS: list[tuple[str, str]] = [
    (r"\b(bijli|electric|electricity|k-?electric|ke|lesco|fesco|iesco|mepco|pesco|qesco|hesco|gepco|tesco|sepco"
     r"|wapda|disco|sui|gas|ssgc|sngpl|ptcl|water|kwsb|wasa|internet|nayatel|stormfibre|utility|util|bill)\b",
     "OUTFLOW_UTILITY"),
    (r"\b(topup|top-?up|load|easyload|scratch|recharge|airtime|mobile[\s-]?balance|jazz|zong|ufone|telenor|warid|scom)\b",
     "OUTFLOW_TOPUP"),
    (r"\b(committee|\bbc\b|\bb\.c\b|rosca|kameti|kamiti|beesi|bisi|pool)\b", "COMMITTEE"),
    (r"\b(rashan|rashon|grocery|groceries|kiryana|karyana|atta|flour|sabzi|vegetable|ration|dukan|store"
     r"|kharcha|kharch|rent|kiraya|school|fees|medicine|dawai|hospital|clinic)\b", "OUTFLOW_ESSENTIAL"),
    (r"\b(salary|tankhwah|tankha|wages|wage|ujrat|payroll|stipend|pension)\b", "INFLOW_SALARY"),
    (r"\b(qr|merchant|shop sale|dukan sale|pos|sale|sales|customer|order|invoice|payment received|received from customer)\b",
     "INFLOW_MERCHANT"),
    (r"\b(restaurant|cafe|food panda|foodpanda|shopping|movie|cinema|game|gaming|entertainment|clothes|fashion|salon)\b",
     "OUTFLOW_DISCRETIONARY"),
    (r"\b(fuel|petrol|diesel|cng|careem|indrive|bykea|uber|yango)\b", "OUTFLOW_DISCRETIONARY"),
]
_P2P_HINT = re.compile(
    r"\b(transfer|trf|iban|account|acct|a/c|wallet|send money|money sent|send to|received from"
    r"|p2p|person to person|raast|ibft|fund transfer|cnic|received|sent)\b",
    re.I,
)
_FOOTER_HINT = re.compile(
    r"\b(opening balance|closing balance|total|subtotal|grand total|statement|generated on|page \d"
    r"|carried forward|brought forward|summary|end of statement)\b",
    re.I,
)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(s).strip().lower())


# --------------------------------------------------------------------------- #
# Loading — CSV (with preamble), JSON, or PDF
# --------------------------------------------------------------------------- #
def _score_header(cells: list[str]) -> int:
    """How many canonical fields these cells look like column headers for."""
    normed = {_norm(c) for c in cells if c}
    hits = 0
    for aliases in COLUMN_ALIASES.values():
        if any(_norm(a) in normed or any(_norm(a) in n or n in _norm(a) for n in normed) for a in aliases):
            hits += 1
    return hits


def _rows_from_dataframe(df: pd.DataFrame) -> list[dict[str, Any]]:
    df = df.dropna(how="all")
    return [
        {str(k): v for k, v in rec.items()}
        for rec in df.to_dict(orient="records")
    ]


def _load_csv_like(text: str) -> list[dict[str, Any]]:
    """Read CSV/TSV, auto-detecting the header row past any preamble rows that
    real bank/wallet statements put on top."""
    sep = "\t" if text.count("\t") > text.count(",") else ","
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []
    # find the line that best looks like a header (scan the first 25)
    best_idx, best_score = 0, -1
    for i, ln in enumerate(lines[:25]):
        cells = next(iter(pd.read_csv(io.StringIO(ln), sep=sep, header=None).values.tolist()), [])
        sc = _score_header([str(c) for c in cells])
        if sc > best_score:
            best_idx, best_score = i, sc
    if best_score < 2:
        best_idx = 0  # give up detecting; assume row 0 is the header
    body = "\n".join(lines[best_idx:])
    df = pd.read_csv(io.StringIO(body), sep=sep, dtype=str, keep_default_na=False)
    df.columns = [str(c).strip() for c in df.columns]
    return _rows_from_dataframe(df)


def _load_pdf(data: bytes) -> list[dict[str, Any]]:
    import pdfplumber

    rows: list[dict[str, Any]] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        # 1) try real tables
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                if not table or len(table) < 2:
                    continue
                header = [str(c or "").strip() for c in table[0]]
                if _score_header(header) < 2:
                    continue
                for raw in table[1:]:
                    rec = {header[i]: (raw[i] if i < len(raw) else "") for i in range(len(header))}
                    rows.append(rec)
        if rows:
            return rows
        # 2) fall back to line parsing: date ... description ... amount [balance]
        line_re = re.compile(
            r"^\s*(?P<date>\d{1,2}[-/ ][A-Za-z0-9]{2,9}[-/ ]\d{2,4})\s+"
            r"(?P<desc>.+?)\s+"
            r"(?P<amount>[-(]?\s*(?:Rs\.?|PKR)?\s*[\d,]+(?:\.\d{1,2})?\s*\)?(?:\s*(?:Cr|Dr))?)"
            r"(?:\s+(?P<balance>[-(]?\s*(?:Rs\.?|PKR)?\s*[\d,]+(?:\.\d{1,2})?\s*\)?))?\s*$",
            re.I,
        )
        for page in pdf.pages:
            for ln in (page.extract_text() or "").splitlines():
                if _FOOTER_HINT.search(ln):
                    continue
                m = line_re.match(ln)
                if m:
                    rows.append(
                        {
                            "date": m.group("date"),
                            "description": m.group("desc").strip(),
                            "amount": m.group("amount").strip(),
                            "balance": (m.group("balance") or "").strip(),
                        }
                    )
    return rows


def _load_rows(filename: str, data: bytes) -> list[dict[str, Any]]:
    if len(data) > settings.max_upload_bytes:
        raise ValueError(f"File exceeds {settings.max_upload_mb} MB limit")
    name_l = (filename or "").lower()

    if name_l.endswith(".pdf") or data[:5] == b"%PDF-":
        rows = _load_pdf(data)
        if not rows:
            raise ValueError(
                "Could not find a transaction table in the PDF. Export the statement "
                "as CSV if possible."
            )
        return rows

    text = data.decode("utf-8-sig", errors="replace")
    stripped = text.lstrip()
    if name_l.endswith(".json") or stripped.startswith(("[", "{")):
        obj = json.loads(text)
        if isinstance(obj, dict):
            for key in ("transactions", "data", "rows", "ledger", "records", "result", "items"):
                if key in obj and isinstance(obj[key], list):
                    obj = obj[key]
                    break
        if not isinstance(obj, list):
            raise ValueError("JSON must be a list of transactions or an object containing one")
        return [dict(r) for r in obj if isinstance(r, dict)]

    return _load_csv_like(text)


# --------------------------------------------------------------------------- #
# Column resolution + value coercion
# --------------------------------------------------------------------------- #
def _resolve_columns(sample_keys: list[str]) -> dict[str, str | None]:
    normed = {_norm(k): k for k in sample_keys if k}
    resolved: dict[str, str | None] = {}
    for canon, aliases in COLUMN_ALIASES.items():
        found = None
        for alias in aliases:  # exact-ish first
            if _norm(alias) in normed:
                found = normed[_norm(alias)]
                break
        if not found:  # loose bidirectional contains
            for nk, orig in normed.items():
                if any(_norm(a) in nk or nk in _norm(a) for a in aliases):
                    found = orig
                    break
        resolved[canon] = found
    return resolved


_TRAIL_CRDR = re.compile(r"\b(cr|dr|db)\b", re.I)


def _to_float(v: Any) -> float | None:
    """Parse '1,234.56', 'Rs 1,234', '(1,234.00)' (negative), '500 Cr', '-'."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    s = str(v).strip()
    if not s or s in {"-", ".", "—", "N/A", "n/a", "nil", "NIL"}:
        return None
    neg = s.startswith("(") and s.endswith(")")
    if _TRAIL_CRDR.search(s):
        # 'Dr' suffix means money out
        if re.search(r"\b(dr|db)\b", s, re.I):
            neg = True
    cleaned = re.sub(r"[^0-9.\-]", "", s)
    if cleaned in {"", "-", ".", "--"}:
        return None
    try:
        val = float(cleaned)
    except ValueError:
        return None
    return -abs(val) if (neg and val >= 0) else val


def _direction(row_dir: Any, amount: float | None, raw_amount_str: str = "") -> str:
    hay = f"{row_dir or ''} {raw_amount_str}".strip().lower()
    if hay:
        if re.search(r"\b(cr|credit|c|in|inflow|deposit|received|paid.?in|money.?in)\b", hay) and not re.search(r"\bdr\b", hay):
            return "credit"
        if re.search(r"\b(dr|db|debit|d|out|outflow|withdrawal|sent|paid.?out|money.?out|purchase)\b", hay):
            return "debit"
        if hay.strip() in {"+"}:
            return "credit"
        if hay.strip() in {"-"}:
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


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def parse_transactions(filename: str, data: bytes) -> dict[str, Any]:
    rows = _load_rows(filename, data)
    if not rows:
        raise ValueError("No transactions found in file")

    # union of keys across the first few rows (PDFs can have ragged rows)
    keys: list[str] = []
    for r in rows[:20]:
        for k in r:
            if k not in keys:
                keys.append(k)
    cols = _resolve_columns(keys)

    has_amount = bool(cols["amount"])
    has_split = bool(cols["debit"] or cols["credit"])
    if not cols["date"] or not (has_amount or has_split):
        raise ValueError(
            "Could not find a date column and an amount (or debit/credit) column. "
            "Accepted date headers include: " + ", ".join(COLUMN_ALIASES["date"][:6]) + " …"
        )

    canonical: list[dict[str, Any]] = []
    for r in rows:
        # amount: single signed column, or separate debit / credit columns
        raw_str = ""
        if has_amount:
            raw_str = str(r.get(cols["amount"], "")).strip()
            raw_amt = _to_float(r.get(cols["amount"]))
        else:
            dv = _to_float(r.get(cols["debit"])) if cols["debit"] else None
            cv = _to_float(r.get(cols["credit"])) if cols["credit"] else None
            if dv:
                raw_amt = -abs(dv)
            elif cv:
                raw_amt = abs(cv)
            else:
                raw_amt = None
        if raw_amt is None or raw_amt == 0:
            continue

        date_val = str(r.get(cols["date"], "")).strip()
        if not date_val or _FOOTER_HINT.search(date_val):
            continue
        try:
            d = dateparser.parse(date_val, dayfirst=True, fuzzy=True)
        except (ValueError, OverflowError, TypeError):
            continue
        if d.year < 2000 or d.year > 2100:
            continue

        counterparty = str(r.get(cols["counterparty"], "") if cols["counterparty"] else "").strip() or "unknown"
        if _FOOTER_HINT.search(counterparty):
            continue
        direction = _direction(r.get(cols["direction"]) if cols["direction"] else None, raw_amt, raw_str)
        channel = str(r.get(cols["channel"], "") if cols["channel"] else "").strip() or None
        balance = _to_float(r.get(cols["balance"])) if cols["balance"] else None

        canonical.append(
            {
                "date": d.date().isoformat(),
                "_dt": d,
                "amount": round(abs(raw_amt), 2),
                "direction": direction,
                "counterparty": counterparty[:80],
                "balance": balance,
                "channel": channel,
                "category": _classify(counterparty, channel, direction),
            }
        )

    if not canonical:
        raise ValueError(
            "Found the columns but no rows parsed into valid dated transactions."
        )

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
