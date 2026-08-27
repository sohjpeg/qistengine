from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas import ScoreRequest, ScoreResponse
from app.services.mock_profiles import MOCK_PROFILES
from app.schemas import MockProfile
from app.services.pipeline import merge_raw_signals, run_scoring

router = APIRouter(prefix="/api/v1", tags=["scoring"])


@router.post("/score", response_model=ScoreResponse)
def score(req: ScoreRequest) -> ScoreResponse:
    raw = merge_raw_signals(req.features, req.bill_fields, req.transaction_aggregates)
    try:
        result = run_scoring(
            raw,
            applicant_id=req.applicant_id,
            archetype_hint=req.archetype_hint,
            tenor_months=req.tenor_months,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    result.pop("_features_used", None)
    return ScoreResponse(**result)


@router.get("/mock/profiles", response_model=list[MockProfile])
def mock_profiles() -> list[MockProfile]:
    out: list[MockProfile] = []
    for p in MOCK_PROFILES:
        out.append(
            MockProfile(
                id=p["id"],
                display_name=p["display_name"],
                headline=p["headline"],
                city=p["city"],
                archetype=p["archetype"],
                business_type=p["business_type"],
                requested_amount_pkr=p["requested_amount_pkr"],
                purpose=p["purpose"],
                applicant=p["applicant"],
                features=p["features"],
                bill_fields=p["bill_fields"],
                monthly_series=[],
                expected_band=p["expected_band"],
            )
        )
    return out
