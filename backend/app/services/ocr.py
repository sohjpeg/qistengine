"""Utility-bill OCR with graceful degradation.

Cascade:
  1. PDF with a text layer      -> pdfplumber
  2. Image / scanned PDF + Tesseract present -> pytesseract --psm 6
  3. anything else              -> deterministic simulated bill (labelled honestly)

The simulated path is seeded from hash(filename + size) so the same upload always
produces the same bill. It returns extraction_method="simulated", confidence 0.0
so the UI shows an amber "simulated extraction" chip.
"""
from __future__ import annotations

import hashlib
import io
import re
from datetime import date, timedelta
from typing import Any

from dateutil import parser as dateparser

from app.config import settings

PATTERNS: dict[str, str] = {
    "consumer_number": r"(?:Consumer|Ref(?:erence)?)\s*(?:No\.?|Number|#)\s*[:\-]?\s*([0-9\-\s]{8,20})",
    "billing_month": r"(?:Bill(?:ing)?\s*Month|Month)\s*[:\-]?\s*([A-Za-z]{3,9}[\s\-]?\d{2,4})",
    "units_consumed": r"(?:Units\s*(?:Consumed)?|Consumption)\s*[:\-]?\s*([\d,]+)",
    "current_charges": r"(?:Current\s*(?:Bill|Charges)|Payable\s*Within\s*Due\s*Date)\s*[:\-]?\s*(?:Rs\.?)?\s*([\d,]+)",
    "arrears": r"(?:Arrears|Previous\s*Balance|Outstanding)\s*[:\-]?\s*(?:Rs\.?)?\s*([\d,]+)",
    "due_date": r"(?:Due\s*Date)\s*[:\-]?\s*(\d{1,2}[\-/\s][A-Za-z0-9]{2,9}[\-/\s]\d{2,4})",
    "payment_date": r"(?:Paid\s*(?:On|Date)|Payment\s*Date)\s*[:\-]?\s*(\d{1,2}[\-/\s][A-Za-z0-9]{2,9}[\-/\s]\d{2,4})",
}

_NUMERIC_FIELDS = {"units_consumed", "current_charges", "arrears"}
_DATE_FIELDS = {"due_date", "payment_date"}

_PROVIDERS = ["K-Electric", "LESCO", "FESCO", "IESCO", "MEPCO", "PESCO", "QESCO", "HESCO", "GEPCO"]


def _tesseract_available() -> bool:
    if settings.ocr_engine == "fallback":
        return False
    try:
        import shutil

        import pytesseract  # noqa: F401

        return shutil.which("tesseract") is not None
    except Exception:
        return False


def _extract_pdf_text(data: bytes) -> str:
    import pdfplumber

    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            text_parts.append(page.extract_text() or "")
    return "\n".join(text_parts)


def _ocr_image(data: bytes) -> str:
    import pytesseract
    from PIL import Image

    img = Image.open(io.BytesIO(data))
    return pytesseract.image_to_string(img, config="--psm 6")


def _parse_fields(text: str) -> tuple[dict[str, Any], dict[str, float]]:
    fields: dict[str, Any] = {}
    confidences: dict[str, float] = {}
    for name, pat in PATTERNS.items():
        m = re.search(pat, text, re.IGNORECASE)
        if not m:
            fields[name] = None
            confidences[name] = 0.0
            continue
        raw = m.group(1).strip()
        if name in _NUMERIC_FIELDS:
            try:
                fields[name] = float(raw.replace(",", "").replace(" ", ""))
                confidences[name] = 0.9
            except ValueError:
                fields[name] = None
                confidences[name] = 0.0
        elif name in _DATE_FIELDS:
            try:
                fields[name] = dateparser.parse(raw, dayfirst=True).date().isoformat()
                confidences[name] = 0.85
            except (ValueError, OverflowError):
                fields[name] = raw
                confidences[name] = 0.4
        else:
            fields[name] = re.sub(r"\s+", " ", raw)
            confidences[name] = 0.8
    return fields, confidences


def _simulate(filename: str, size: int) -> tuple[dict[str, Any], dict[str, float]]:
    h = hashlib.sha256(f"{filename}|{size}".encode()).digest()
    seed = int.from_bytes(h[:8], "big")

    def pick(lo: int, hi: int, salt: int) -> int:
        return lo + (seed // (salt or 1)) % (hi - lo + 1)

    provider = _PROVIDERS[seed % len(_PROVIDERS)]
    units = pick(120, 780, 3)
    tariff = 22 + (seed % 9)
    current = round(units * tariff + pick(200, 1500, 7), -1)
    arrears = 0 if seed % 3 else pick(500, 4000, 11)
    due = date.today().replace(day=15) + timedelta(days=pick(-40, 5, 13))
    paid_offset = pick(-6, 14, 17)
    paid = due + timedelta(days=paid_offset)
    consumer = f"{pick(10, 99, 2)}-{pick(10000, 99999, 5)}-{pick(1000000, 9999999, 9)}"
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    billing_month = f"{months[due.month - 1]} {due.year}"

    fields = {
        "provider": provider,
        "consumer_number": consumer,
        "billing_month": billing_month,
        "units_consumed": float(units),
        "current_charges": float(current),
        "arrears": float(arrears),
        "due_date": due.isoformat(),
        "payment_date": paid.isoformat(),
    }
    confidences = {k: 0.0 for k in fields}
    return fields, confidences


def _derive_features(fields: dict[str, Any]) -> dict[str, float]:
    """Turn a single bill into the slice of utility features it can support."""
    out: dict[str, float] = {}
    due = fields.get("due_date")
    paid = fields.get("payment_date")
    days_late = 0.0
    if due and paid:
        try:
            d0 = dateparser.parse(str(due)).date()
            d1 = dateparser.parse(str(paid)).date()
            days_late = max(0.0, min(60.0, (d1 - d0).days))
        except (ValueError, OverflowError):
            days_late = 0.0
    out["utility_avg_days_late"] = days_late
    out["utility_on_time_ratio"] = 1.0 if days_late <= 0 else max(0.0, 1.0 - days_late / 30.0)
    out["utility_disconnection_events"] = 1.0 if (fields.get("arrears") or 0) > 3000 else 0.0
    out["utility_months_observed"] = 1.0  # a single bill; caller should merge history
    return out


def parse_bill(filename: str, data: bytes) -> dict[str, Any]:
    size = len(data)
    if size > settings.max_upload_bytes:
        raise ValueError(f"File exceeds {settings.max_upload_mb} MB limit")

    name_l = filename.lower()
    method = "simulated"
    text = ""

    try:
        if name_l.endswith(".pdf"):
            text = _extract_pdf_text(data)
            if len(text.strip()) >= 40:
                method = "pdf_text"
            elif _tesseract_available():
                text = _ocr_image(data)
                method = "tesseract"
        elif name_l.endswith((".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")):
            if _tesseract_available():
                text = _ocr_image(data)
                method = "tesseract"
    except Exception:
        method = "simulated"
        text = ""

    if method == "simulated":
        fields, confidences = _simulate(filename, size)
    else:
        fields, confidences = _parse_fields(text)
        if all(v is None for k, v in fields.items()):
            method = "simulated"
            fields, confidences = _simulate(filename, size)

    overall = 0.0 if method == "simulated" else round(
        sum(confidences.values()) / max(len(confidences), 1), 3
    )
    derived = _derive_features(fields)

    return {
        "filename": filename,
        "extraction_method": method,
        "confidence": overall,
        "fields": [
            {"name": k, "value": v, "confidence": confidences.get(k, 0.0)}
            for k, v in fields.items()
        ],
        "derived_features": derived,
    }
