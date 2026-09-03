#!/usr/bin/env python3
"""Write the six downloadable demo bill + transaction-log pairs into data/samples/.

Three bills are text-layer PDFs (exercise the pdfplumber path), three are PNG
images (exercise the Tesseract / simulated-fallback path). Each pair matches one
of the six hand-built demo profiles so a judge can drag the files straight back
into the applicant portal.
"""
from __future__ import annotations

import csv
import io
import random
import sys
from datetime import date, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.mock_profiles import MOCK_PROFILES  # noqa: E402

SAMPLES = BACKEND_ROOT / "data" / "samples"

# Fixed reference date so the generated files are byte-reproducible run to run
# (no git churn) and the demo always shows the same bill dates.
REF_DATE = date(2026, 8, 20)

# which profile id -> (bill format, wallet)
LAYOUT = {
    "ayesha-lahore-tailoring": ("pdf", "JazzCash"),
    "bilal-karachi-kiryana": ("pdf", "EasyPaisa"),
    "farhan-rawalpindi-ridehailing": ("png", "JazzCash"),
    "nasreen-multan-homefood": ("pdf", "EasyPaisa"),
    "imran-faisalabad-dailywage": ("png", "SadaPay"),
    "zubair-peshawar-autoparts": ("png", "DigitalKhata"),
}

_SLUG = {
    "kiryana_merchant": "kiryana",
    "daily_wage_worker": "dailywage",
    "home_based_producer": "homebased",
    "ride_hailing_driver": "ridehailing",
}


def _pdf_bytes(lines: list[str]) -> bytes:
    """Minimal single-page PDF with a Helvetica text layer pdfplumber can read."""
    def esc(s: str) -> str:
        return s.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")

    content = ["BT", "/F1 11 Tf", "50 800 Td", "13 TL"]
    for i, ln in enumerate(lines):
        content.append(f"({esc(ln)}) Tj" if i == 0 else f"T* ({esc(ln)}) Tj")
    content.append("ET")
    stream = "\n".join(content).encode("latin-1", "replace")

    objs: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for i, body in enumerate(objs, start=1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % i + body + b"\nendobj\n")
    xref_pos = out.tell()
    out.write(b"xref\n0 %d\n" % (len(objs) + 1))
    out.write(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.write(b"%010d 00000 n \n" % off)
    out.write(
        b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF"
        % (len(objs) + 1, xref_pos)
    )
    return out.getvalue()


def _png_bytes(lines: list[str]) -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (760, 24 * len(lines) + 60), "white")
    d = ImageDraw.Draw(img)
    y = 24
    for ln in lines:
        d.text((28, y), ln, fill=(17, 19, 28))
        y += 24
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _bill_lines(profile: dict) -> list[str]:
    bf = profile["bill_fields"]
    rng = random.Random(profile["id"])
    due = REF_DATE.replace(day=15) - timedelta(days=rng.randint(0, 25))
    on_time = profile["features"].get("utility_on_time_ratio", 0.7)
    paid = due - timedelta(days=rng.randint(1, 4)) if rng.random() < on_time else due + timedelta(days=rng.randint(2, 18))
    arrears = int(bf.get("arrears", 0))
    current = int(bf["current_charges"])
    consumer = f"{rng.randint(10,99)}-{rng.randint(10000,99999)}-{rng.randint(1000000,9999999)}"
    months = ["January", "February", "March", "April", "May", "June",
              "July", "August", "September", "October", "November", "December"]
    return [
        f"{bf['provider']}  -  ELECTRICITY CONSUMER BILL",
        "Islamic Republic of Pakistan  |  DISCO copy",
        "-" * 58,
        f"Consumer Name       : {profile['applicant']['full_name']}",
        f"Consumer Number     : {consumer}",
        f"Address             : {profile['city']}, Pakistan",
        f"Billing Month       : {months[due.month - 1]} {due.year}",
        f"Units Consumed      : {int(bf['units_consumed'])}",
        "-" * 58,
        f"Current Charges     : Rs {current:,}",
        f"Arrears             : Rs {arrears:,}",
        f"Payable Within Due Date : Rs {current + arrears:,}",
        f"Payable After Due Date  : Rs {int((current + arrears) * 1.1):,}",
        f"Due Date            : {due.strftime('%d-%b-%Y')}",
        f"Payment Date        : {paid.strftime('%d-%b-%Y')}",
        "-" * 58,
        "This is a demonstration document generated for QistEngine.",
        "Not a genuine utility bill.",
    ]


def _txn_rows(profile: dict, wallet: str) -> list[dict]:
    f = profile["features"]
    rng = random.Random(profile["id"] + wallet)
    inflow = f.get("monthly_inflow_pkr", 50000)
    outflow = f.get("monthly_outflow_pkr", 40000)
    merchant_share = f.get("merchant_inflow_share", 0.4)
    committee = f.get("committee_participation", 0) >= 0.5
    rows: list[dict] = []
    balance = max(1500, inflow * f.get("balance_floor_ratio", 0.06) + 2500)
    start = REF_DATE.replace(day=1) - timedelta(days=95)

    # header aliases vary by wallet so the parser's tolerance is exercised
    for month in range(3):
        m_start = start + timedelta(days=30 * month)
        # inflows
        n_in = max(4, int(f.get("txn_frequency_monthly", 40) * 0.45))
        for i in range(n_in):
            d = m_start + timedelta(days=rng.randint(0, 27))
            amt = max(50.0, round(inflow / n_in * rng.uniform(0.55, 1.45), -1))
            is_merchant = rng.random() < merchant_share
            desc = rng.choice(["QR sale customer", "Shop sale", "POS receipt"]) if is_merchant else rng.choice(
                ["Transfer received", "Cash in from Bilal", "P2P received wallet"]
            )
            balance += amt
            rows.append({"date": d, "amount": amt, "dir": "credit", "party": desc, "balance": round(balance)})
        # outflows — total across the month must land near `outflow`
        n_out = max(6, int(f.get("txn_frequency_monthly", 40) * 0.55))
        per = outflow / n_out
        for i in range(n_out):
            d = m_start + timedelta(days=rng.randint(0, 27))
            cat = rng.random()
            if cat < 0.08:
                amt = round(per * rng.uniform(1.5, 2.5), -1)
                desc = f"{profile['bill_fields']['provider']} bijli bill"
            elif cat < 0.20:
                amt = round(rng.uniform(100, 600), -1)
                desc = "Mobile easyload topup"
            elif cat < 0.30 and committee:
                amt = round(rng.uniform(2000, 5000), -1)
                desc = "Committee BC contribution"
            elif cat < 0.62:
                amt = round(per * rng.uniform(0.5, 1.3), -1)
                desc = rng.choice(["Rashan grocery kharcha", "Wholesale stock", "Atta flour"])
            else:
                amt = round(per * rng.uniform(0.3, 1.0), -1)
                desc = rng.choice(["Transfer sent", "P2P sent", "Fuel", "Misc kharcha"])
            amt = max(50.0, amt)
            balance = max(80, balance - amt)
            rows.append({"date": d, "amount": -amt, "dir": "debit", "party": desc, "balance": round(balance)})

    rows.sort(key=lambda r: r["date"])
    return rows


def _write_csv(path: Path, rows: list[dict], wallet: str) -> None:
    # each wallet uses slightly different headers
    if wallet == "JazzCash":
        header = ["txn_date", "amount", "type", "counterparty", "balance"]
        keymap = {"txn_date": "date", "amount": "amount", "type": "dir", "counterparty": "party", "balance": "balance"}
    elif wallet == "EasyPaisa":
        header = ["Date", "Amount", "Debit/Credit", "Detail", "Running Balance"]
        keymap = {"Date": "date", "Amount": "amount", "Debit/Credit": "dir", "Detail": "party", "Running Balance": "balance"}
    elif wallet == "SadaPay":
        header = ["transaction_date", "txn_amount", "direction", "description", "closing_balance"]
        keymap = {"transaction_date": "date", "txn_amount": "amount", "direction": "dir", "description": "party", "closing_balance": "balance"}
    else:  # DigitalKhata hand-kept ledger, Urdu-ish headers, no direction column
        header = ["tarikh", "rakam", "tafseel", "balance"]
        keymap = {"tarikh": "date", "rakam": "amount", "tafseel": "party", "balance": "balance"}

    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        for r in rows:
            line = []
            for col in header:
                src = keymap[col]
                if src == "date":
                    line.append(r["date"].strftime("%d-%m-%Y"))
                elif src == "dir":
                    line.append("Credit" if r["dir"] == "credit" else "Debit")
                elif src == "amount":
                    # DigitalKhata keeps signed amounts, others positive
                    line.append(r["amount"] if "dir" not in keymap.values() else abs(r["amount"]))
                else:
                    line.append(r[src])
            w.writerow(line)


def main() -> None:
    SAMPLES.mkdir(parents=True, exist_ok=True)
    for p in MOCK_PROFILES:
        fmt, wallet = LAYOUT[p["id"]]
        city = p["city"].lower()
        arch = _SLUG.get(p["archetype"], p["archetype"])
        prov = p["bill_fields"]["provider"].lower().replace("-", "")
        bill_name = f"{city}_{arch}_{prov}_bill.{ 'pdf' if fmt == 'pdf' else 'png' }"
        ledger_name = f"{city}_{arch}_{wallet.lower()}_ledger.csv"

        lines = _bill_lines(p)
        data = _pdf_bytes(lines) if fmt == "pdf" else _png_bytes(lines)
        (SAMPLES / bill_name).write_bytes(data)

        rows = _txn_rows(p, wallet)
        _write_csv(SAMPLES / ledger_name, rows, wallet)
        print(f"[samples] {bill_name}  +  {ledger_name}  ({len(rows)} txns)")

    print(f"[samples] wrote {len(MOCK_PROFILES) * 2} files -> {SAMPLES}")


if __name__ == "__main__":
    main()
