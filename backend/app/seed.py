"""Seed the SQLite database with a demo portfolio.

Idempotent: wipes the QistEngine tables and rebuilds them. Runs the six hand-built
mock profiles plus ~30 sampled synthetic profiles through the real scoring
pipeline, then records decisions on most of them so /analytics has data.

    python -m app.seed
"""
from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from sqlmodel import Session, delete, select

from app.database import engine, init_db
from app.ml.registry import registry
from app.models import Applicant, Application, Decision, Document, ScoreResult
from app.routers.applications import mask_cnic, mask_phone
from app.services.feature_engineering import FEATURE_ORDER
from app.services.mock_profiles import MOCK_PROFILES
from app.services.pipeline import run_scoring

BACKEND_ROOT = Path(__file__).resolve().parent.parent
RAW_CSV = BACKEND_ROOT / "data" / "raw" / "synthetic_profiles.csv"
SEED = 42

_FIRST_M = ["Ahmed", "Bilal", "Usman", "Hamza", "Faisal", "Kashif", "Naveed", "Adnan", "Rizwan", "Tariq"]
_FIRST_F = ["Ayesha", "Fatima", "Nasreen", "Saima", "Rabia", "Kiran", "Sadia", "Nadia", "Hina", "Uzma"]
_LAST = ["Khan", "Ahmed", "Malik", "Bhatti", "Chaudhry", "Sheikh", "Qureshi", "Butt", "Awan", "Gondal"]
_BUSINESS = {
    "kiryana_merchant": "Neighbourhood grocery",
    "daily_wage_worker": "Construction & transport labour",
    "home_based_producer": "Home-based production",
    "ride_hailing_driver": "Ride-hailing driver",
}


def _wipe(session: Session) -> None:
    for model in (Decision, Document, ScoreResult, Application, Applicant):
        session.exec(delete(model))
    session.commit()


def _persist_scored(
    session: Session,
    *,
    applicant: Applicant,
    requested: float,
    purpose: str,
    raw: dict,
    archetype: str,
    submitted_at: datetime,
    bill_fields: dict | None = None,
) -> tuple[Application, ScoreResult]:
    session.add(applicant)
    session.flush()
    app_row = Application(
        applicant_id=applicant.id,
        status="SCORED",
        requested_amount_pkr=requested,
        purpose=purpose,
        submitted_at=submitted_at,
    )
    session.add(app_row)
    session.flush()

    result = run_scoring(raw, applicant_id=app_row.id, archetype_hint=archetype)
    feats = result.pop("_features_used", {})
    sr = ScoreResult(
        application_id=app_row.id,
        score=result["score"],
        probability_of_default=result["probability_of_default"],
        risk_band=result["risk_band"],
        model_version=result["model_version"],
        features_json={
            **feats,
            "_ledger_lines": result["ledger_lines"],
            "_base_contribution": result["base_contribution"],
            "_adverse": result["adverse_action_codes"],
            "_portfolio_median": result["portfolio_median_metrics"],
        },
        reason_codes_json=result["reason_codes"],
        qist_limit_json=result["qist_limit"],
        behavioral_metrics_json=result["behavioral_metrics"],
        monthly_series_json=result["monthly_series"],
        data_gaps_json=result["data_gaps"],
        confidence=result["confidence"],
        scored_at=submitted_at,
    )
    session.add(sr)
    if bill_fields:
        session.add(
            Document(
                application_id=app_row.id,
                doc_type="UTILITY_BILL",
                filename=f"{applicant.city.lower()}_{archetype}_bill.pdf",
                extraction_method="simulated",
                confidence=0.0,
                extracted_json=bill_fields,
                uploaded_at=submitted_at,
            )
        )
    return app_row, sr


def _decide(session: Session, app_row: Application, sr: ScoreResult, rng: random.Random) -> None:
    ql = sr.qist_limit_json or {}
    safe = ql.get("safe_installment_pkr") or 0
    band = sr.risk_band

    if band == "LOW":
        decision, status = "APPROVE", "APPROVED"
        amt = ql.get("principal_pkr", 0)
        inst = safe
        override = False
        note = "Auto-approved within policy."
    elif band == "MEDIUM":
        decision, status = ("APPROVE", "APPROVED") if rng.random() < 0.8 else ("REQUEST_INFO", "NEEDS_INFO")
        amt = ql.get("principal_pkr", 0)
        inst = safe
        override = False
        note = "Manual review cleared." if decision == "APPROVE" else "Requested 3 more months of ledger data."
    elif band == "HIGH":
        if rng.random() < 0.45:
            decision, status = "APPROVE_MODIFIED", "APPROVED"
            amt = int(ql.get("principal_pkr", 0) * 0.7)
            inst = safe
            override = False
            note = "Approved at a reduced principal with guarantor on file."
        else:
            decision, status = "REJECT", "REJECTED"
            amt = inst = None
            override = False
            note = "Declined: expense burden above policy for the HIGH band."
    else:  # VERY_HIGH
        if rng.random() < 0.2:
            decision, status = "APPROVE_MODIFIED", "APPROVED"
            amt = min(20000, ql.get("principal_pkr", 0) or 20000)
            inst = max(2000, safe)
            override = True
            note = "Override: long-standing customer, small starter Qist against branch manager sign-off."
        else:
            decision, status = "REJECT", "REJECTED"
            amt = inst = None
            override = False
            note = "Declined. Financial-literacy referral issued."

    decided_at = app_row.submitted_at + timedelta(hours=rng.randint(2, 60))
    session.add(
        Decision(
            application_id=app_row.id,
            decision=decision,
            approved_amount_pkr=amt,
            approved_installment_pkr=inst,
            tenor_months=ql.get("tenor_months"),
            officer_note=note,
            override_flag=override,
            created_at=decided_at,
        )
    )
    app_row.status = status
    app_row.decided_at = decided_at
    app_row.decided_by = rng.choice(["s.raza", "m.iqbal", "f.tariq"])
    session.add(app_row)


def main() -> None:
    init_db()
    registry.load()
    if not registry.loaded:
        print(f"[seed] model not loaded: {registry.error}", file=sys.stderr)
        sys.exit(1)

    rng = random.Random(SEED)
    now = datetime.now(timezone.utc)

    with Session(engine) as session:
        _wipe(session)

        # --- 6 hand-built demo profiles (most recent) ---
        for i, p in enumerate(MOCK_PROFILES):
            a = p["applicant"]
            applicant = Applicant(
                full_name=a["full_name"],
                cnic_masked=mask_cnic(a["cnic"]),
                phone_masked=mask_phone(a["phone"]),
                city=a["city"],
                archetype=a["archetype"],
                business_type=a["business_type"],
                dependents_count=a["dependents_count"],
                has_fixed_premises=a["has_fixed_premises"],
                created_at=now - timedelta(hours=i),
            )
            app_row, sr = _persist_scored(
                session,
                applicant=applicant,
                requested=p["requested_amount_pkr"],
                purpose=p["purpose"],
                raw=dict(p["features"]),
                archetype=a["archetype"],
                submitted_at=now - timedelta(hours=i),
                bill_fields=p["bill_fields"],
            )
            # leave the six demo apps un-decided so the queue has live work
        session.commit()

        # --- ~30 sampled synthetic profiles, decided ---
        if RAW_CSV.exists():
            df = pd.read_csv(RAW_CSV)
            sample = df.sample(n=min(30, len(df)), random_state=SEED).reset_index(drop=True)
            for idx, row in sample.iterrows():
                archetype = row["archetype"]
                female = rng.random() < (0.6 if archetype == "home_based_producer" else 0.15)
                first = rng.choice(_FIRST_F if female else _FIRST_M)
                name = f"{first} {rng.choice(_LAST)}"
                submitted = now - timedelta(days=rng.randint(1, 21), hours=rng.randint(0, 23))
                applicant = Applicant(
                    full_name=name,
                    cnic_masked=mask_cnic(f"{rng.randint(10000,99999)}{rng.randint(1000000,9999999)}{rng.randint(0,9)}"),
                    phone_masked=mask_phone(f"03{rng.randint(100000000, 999999999)}"),
                    city=row["city"],
                    archetype=archetype,
                    business_type=_BUSINESS.get(archetype, "Micro-enterprise"),
                    dependents_count=int(row["dependents_count"]),
                    has_fixed_premises=bool(row["has_fixed_premises"] >= 0.5),
                    created_at=submitted,
                )
                raw = {f: float(row[f]) for f in FEATURE_ORDER}
                requested = float(rng.choice([30000, 45000, 60000, 80000, 100000, 120000]))
                app_row, sr = _persist_scored(
                    session,
                    applicant=applicant,
                    requested=requested,
                    purpose=rng.choice(
                        ["Inventory purchase", "Equipment upgrade", "Working capital",
                         "Seasonal stock", "Vehicle repair", "Premises deposit"]
                    ),
                    raw=raw,
                    archetype=archetype,
                    submitted_at=submitted,
                )
                _decide(session, app_row, sr, rng)
            session.commit()

        n_app = len(session.exec(select(Application)).all())
        n_dec = len(session.exec(select(Decision)).all())
        print(f"[seed] {n_app} applications, {n_dec} decisions written to the demo database.")


if __name__ == "__main__":
    main()
