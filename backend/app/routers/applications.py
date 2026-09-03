from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, func, select

from app.database import get_session
from app.models import Applicant, Application, Decision, Document, ScoreResult
from app.schemas import (
    ApplicantOut,
    ApplicationCreate,
    ApplicationDetail,
    ApplicationSummary,
    DecisionCreate,
    DecisionOut,
    DocumentOut,
    PaginatedApplications,
    ScoreResponse,
)
from app.services.pipeline import merge_raw_signals, run_scoring
from app.services.scorecard import score_to_band

router = APIRouter(prefix="/api/v1", tags=["applications"])


def mask_cnic(cnic: str) -> str:
    digits = re.sub(r"\D", "", cnic or "")
    if len(digits) >= 13:
        return f"*****-*******-{digits[-1]}"
    return "*****-*******-*"


def mask_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) >= 4:
        return f"******{digits[-4:]}"
    return "**********"


def _score_payload_from_row(sr: ScoreResult) -> ScoreResponse:
    return ScoreResponse(
        application_id=sr.application_id,
        score=sr.score,
        probability_of_default=sr.probability_of_default,
        risk_band=sr.risk_band,
        band_label=score_to_band(sr.score).label,
        confidence=sr.confidence,
        qist_limit=sr.qist_limit_json,
        reason_codes=[rc for rc in sr.reason_codes_json if rc.get("feature")][:8],
        ledger_lines=sr.features_json.get("_ledger_lines", []),
        base_contribution=sr.features_json.get("_base_contribution", 660.0),
        adverse_action_codes=sr.features_json.get("_adverse", []),
        behavioral_metrics=sr.behavioral_metrics_json,
        portfolio_median_metrics=sr.features_json.get("_portfolio_median", sr.behavioral_metrics_json),
        monthly_series=sr.monthly_series_json,
        data_gaps=sr.data_gaps_json,
        model_version=sr.model_version,
        scored_at=sr.scored_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


@router.post("/applications", response_model=ApplicationDetail, status_code=201)
def create_application(body: ApplicationCreate, session: Session = Depends(get_session)) -> ApplicationDetail:
    a = body.applicant
    applicant = Applicant(
        full_name=a.full_name,
        cnic_masked=mask_cnic(a.cnic),
        phone_masked=mask_phone(a.phone),
        city=a.city,
        archetype=a.archetype,
        business_type=a.business_type,
        dependents_count=a.dependents_count,
        has_fixed_premises=a.has_fixed_premises,
    )
    session.add(applicant)
    session.flush()

    application = Application(
        applicant_id=applicant.id,
        status="PENDING",
        requested_amount_pkr=body.requested_amount_pkr,
        purpose=body.purpose,
    )
    session.add(application)
    session.flush()

    raw = merge_raw_signals(body.features, body.bill_fields, body.transaction_aggregates)
    raw.setdefault("dependents_count", a.dependents_count)
    raw.setdefault("has_fixed_premises", 1.0 if a.has_fixed_premises else 0.0)
    monthly = [m.model_dump() for m in body.monthly_series] if body.monthly_series else None

    try:
        result = run_scoring(
            raw,
            applicant_id=application.id,
            archetype_hint=a.archetype,
            monthly_series=monthly,
            tenor_months=body.tenor_months,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    features_used = result.pop("_features_used", {})
    sr = ScoreResult(
        application_id=application.id,
        score=result["score"],
        probability_of_default=result["probability_of_default"],
        risk_band=result["risk_band"],
        model_version=result["model_version"],
        features_json={
            **features_used,
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
    )
    session.add(sr)

    if body.bill_fields:
        session.add(
            Document(
                application_id=application.id,
                doc_type="UTILITY_BILL",
                filename=body.bill_fields.get("_filename", "supplied-bill.json"),
                extraction_method=body.bill_fields.get("_extraction_method", "supplied"),
                confidence=float(body.bill_fields.get("_confidence", 0.0) or 0.0),
                extracted_json={k: v for k, v in body.bill_fields.items() if not k.startswith("_")},
            )
        )
    if body.transaction_aggregates:
        session.add(
            Document(
                application_id=application.id,
                doc_type="TRANSACTION_LOG",
                filename=body.transaction_aggregates.get("_filename", "supplied-ledger.json"),
                extraction_method="supplied",
                confidence=1.0,
                extracted_json={k: v for k, v in body.transaction_aggregates.items() if not k.startswith("_")},
            )
        )

    application.status = "SCORED"
    session.add(application)
    session.commit()

    return _detail(application.id, session)


@router.get("/applications", response_model=PaginatedApplications)
def list_applications(
    session: Session = Depends(get_session),
    status: str | None = None,
    risk_band: str | None = None,
    city: str | None = None,
    archetype: str | None = None,
    sort: Literal["score", "date"] = "date",
    order: Literal["asc", "desc"] = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> PaginatedApplications:
    stmt = select(Application, Applicant, ScoreResult).join(
        Applicant, Applicant.id == Application.applicant_id
    ).join(ScoreResult, ScoreResult.application_id == Application.id, isouter=True)

    if status:
        stmt = stmt.where(Application.status == status)
    if city:
        stmt = stmt.where(Applicant.city == city)
    if archetype:
        stmt = stmt.where(Applicant.archetype == archetype)
    if risk_band:
        stmt = stmt.where(ScoreResult.risk_band == risk_band)

    rows = session.exec(stmt).all()

    def sort_key(r):
        _app, _appl, _sr = r
        return (_sr.score if _sr else -1) if sort == "score" else _app.submitted_at.timestamp()

    rows.sort(key=sort_key, reverse=(order == "desc"))
    total = len(rows)
    start = (page - 1) * page_size
    page_rows = rows[start : start + page_size]

    latest_decision: dict[str, Decision] = {}
    if page_rows:
        ids = [a.id for a, _, _ in page_rows]
        for d in session.exec(select(Decision).where(Decision.application_id.in_(ids))).all():
            latest_decision[d.application_id] = d

    items = []
    for app_row, appl, sr in page_rows:
        ql = sr.qist_limit_json if sr else {}
        items.append(
            ApplicationSummary(
                id=app_row.id,
                applicant_name=appl.full_name,
                city=appl.city,
                archetype=appl.archetype,
                status=app_row.status,
                requested_amount_pkr=app_row.requested_amount_pkr,
                score=sr.score if sr else None,
                risk_band=sr.risk_band if sr else None,
                safe_installment_pkr=ql.get("safe_installment_pkr"),
                principal_pkr=ql.get("principal_pkr"),
                submitted_at=app_row.submitted_at,
                decided_at=app_row.decided_at,
                override_flag=latest_decision.get(app_row.id).override_flag
                if app_row.id in latest_decision
                else False,
            )
        )
    return PaginatedApplications(items=items, total=total, page=page, page_size=page_size)


def _detail(application_id: str, session: Session) -> ApplicationDetail:
    app_row = session.get(Application, application_id)
    if not app_row:
        raise HTTPException(status_code=404, detail="Application not found")
    appl = session.get(Applicant, app_row.applicant_id)
    docs = session.exec(select(Document).where(Document.application_id == application_id)).all()
    sr = session.exec(
        select(ScoreResult).where(ScoreResult.application_id == application_id)
    ).first()
    dec = session.exec(
        select(Decision).where(Decision.application_id == application_id).order_by(Decision.created_at.desc())
    ).first()

    return ApplicationDetail(
        id=app_row.id,
        status=app_row.status,
        requested_amount_pkr=app_row.requested_amount_pkr,
        purpose=app_row.purpose,
        submitted_at=app_row.submitted_at,
        decided_at=app_row.decided_at,
        decided_by=app_row.decided_by,
        applicant=ApplicantOut(**appl.model_dump()),
        documents=[DocumentOut(**d.model_dump()) for d in docs],
        score_result=_score_payload_from_row(sr) if sr else None,
        decision=DecisionOut(**dec.model_dump()) if dec else None,
    )


@router.get("/applications/{application_id}", response_model=ApplicationDetail)
def get_application(application_id: str, session: Session = Depends(get_session)) -> ApplicationDetail:
    return _detail(application_id, session)


@router.patch("/applications/{application_id}/decision", response_model=ApplicationDetail)
def record_decision(
    application_id: str, body: DecisionCreate, session: Session = Depends(get_session)
) -> ApplicationDetail:
    app_row = session.get(Application, application_id)
    if not app_row:
        raise HTTPException(status_code=404, detail="Application not found")
    sr = session.exec(select(ScoreResult).where(ScoreResult.application_id == application_id)).first()
    if not sr:
        raise HTTPException(status_code=409, detail="Application has not been scored yet")

    ql = sr.qist_limit_json or {}
    safe_installment = ql.get("safe_installment_pkr") or 0
    approving = body.decision in ("APPROVE", "APPROVE_MODIFIED")
    above_safe = bool(
        approving
        and body.approved_installment_pkr is not None
        and body.approved_installment_pkr > safe_installment
    )
    against_band = approving and sr.risk_band == "VERY_HIGH"
    override = above_safe or against_band

    if override and not (body.justification and body.justification.strip()):
        raise HTTPException(
            status_code=422,
            detail="A written justification is required to approve above the safe limit or on a VERY_HIGH band.",
        )

    note = body.officer_note
    if body.justification:
        note = (note + "\n\nOverride justification: " + body.justification).strip()

    decision = Decision(
        application_id=application_id,
        decision=body.decision,
        approved_amount_pkr=body.approved_amount_pkr,
        approved_installment_pkr=body.approved_installment_pkr,
        tenor_months=body.tenor_months or ql.get("tenor_months"),
        officer_note=note,
        override_flag=override,
    )
    session.add(decision)

    status_map = {
        "APPROVE": "APPROVED",
        "APPROVE_MODIFIED": "APPROVED",
        "REJECT": "REJECTED",
        "REQUEST_INFO": "NEEDS_INFO",
    }
    app_row.status = status_map[body.decision]
    app_row.decided_at = datetime.now(timezone.utc)
    app_row.decided_by = body.decided_by
    session.add(app_row)
    session.commit()

    return _detail(application_id, session)
