from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.models import Applicant, Application, Decision, ScoreResult
from app.schemas import MetricsResponse
from app.services.scorecard import BANDS

router = APIRouter(prefix="/api/v1", tags=["metrics"])

_BAND_KEYS = [b.key for b in BANDS]
_HIST_BINS = [(300, 400), (400, 460), (460, 520), (520, 560), (560, 600),
              (600, 640), (640, 680), (680, 720), (720, 780), (780, 851)]


@router.get("/metrics", response_model=MetricsResponse)
def metrics(session: Session = Depends(get_session)) -> MetricsResponse:
    apps = session.exec(select(Application)).all()
    scores = session.exec(select(ScoreResult)).all()
    decisions = session.exec(select(Decision)).all()
    applicants = {a.id: a for a in session.exec(select(Applicant)).all()}

    score_by_app = {s.application_id: s for s in scores}
    total = len(apps)
    today = datetime.now(timezone.utc).date()
    today_count = sum(1 for a in apps if a.submitted_at.date() == today)

    decided = [a for a in apps if a.status in ("APPROVED", "REJECTED")]
    approved = [a for a in apps if a.status == "APPROVED"]
    approval_rate = (len(approved) / len(decided)) if decided else 0.0

    all_scores = [s.score for s in scores]
    mean_score = (sum(all_scores) / len(all_scores)) if all_scores else 0.0

    # portfolio expected loss = sum(pd * approved_principal) over approved apps
    latest_dec: dict[str, Decision] = {}
    for d in sorted(decisions, key=lambda x: x.created_at):
        latest_dec[d.application_id] = d
    exp_loss = 0.0
    for a in approved:
        s = score_by_app.get(a.id)
        d = latest_dec.get(a.id)
        if not s:
            continue
        principal = (d.approved_amount_pkr if d and d.approved_amount_pkr else
                     (s.qist_limit_json or {}).get("principal_pkr", 0) or 0)
        exp_loss += s.probability_of_default * float(principal) * 0.6  # assume 60% LGD

    override_count = sum(1 for d in latest_dec.values() if d.override_flag)
    override_rate = (override_count / len(latest_dec)) if latest_dec else 0.0

    band_dist = defaultdict(int)
    for s in scores:
        band_dist[s.risk_band] += 1

    histogram = []
    for lo, hi in _HIST_BINS:
        c = sum(1 for sc in all_scores if lo <= sc < hi)
        # band colour for the bin midpoint
        mid = (lo + hi) // 2
        band = next((b.key for b in BANDS if b.lo <= mid <= b.hi), "VERY_HIGH")
        histogram.append({"range": f"{lo}-{hi - 1}", "count": c, "band": band})

    # approval rate by band
    by_band_decided = defaultdict(list)
    for a in decided:
        s = score_by_app.get(a.id)
        if s:
            by_band_decided[s.risk_band].append(1 if a.status == "APPROVED" else 0)
    approval_by_band = {
        k: round(sum(v) / len(v), 4) if v else 0.0 for k, v in by_band_decided.items()
    }
    for k in _BAND_KEYS:
        approval_by_band.setdefault(k, 0.0)

    # city breakdown
    city_agg = defaultdict(lambda: {"count": 0, "score_sum": 0, "approved": 0, "decided": 0})
    for a in apps:
        appl = applicants.get(a.applicant_id)
        if not appl:
            continue
        c = city_agg[appl.city]
        c["count"] += 1
        s = score_by_app.get(a.id)
        if s:
            c["score_sum"] += s.score
        if a.status in ("APPROVED", "REJECTED"):
            c["decided"] += 1
            if a.status == "APPROVED":
                c["approved"] += 1
    city_breakdown = [
        {
            "city": city,
            "applications": v["count"],
            "mean_score": round(v["score_sum"] / v["count"], 1) if v["count"] else 0,
            "approval_rate": round(v["approved"] / v["decided"], 4) if v["decided"] else 0.0,
        }
        for city, v in sorted(city_agg.items())
    ]

    # override trend by day
    trend_agg = defaultdict(lambda: {"decisions": 0, "overrides": 0})
    for d in latest_dec.values():
        key = d.created_at.date().isoformat()
        trend_agg[key]["decisions"] += 1
        if d.override_flag:
            trend_agg[key]["overrides"] += 1
    override_trend = [
        {
            "date": k,
            "decisions": v["decisions"],
            "overrides": v["overrides"],
            "rate": round(v["overrides"] / v["decisions"], 4) if v["decisions"] else 0.0,
        }
        for k, v in sorted(trend_agg.items())
    ]

    return MetricsResponse(
        applications_total=total,
        applications_today=today_count,
        approval_rate=round(approval_rate, 4),
        mean_score=round(mean_score, 1),
        portfolio_expected_loss_pkr=round(exp_loss, 0),
        override_rate=round(override_rate, 4),
        band_distribution={k: band_dist.get(k, 0) for k in _BAND_KEYS},
        score_histogram=histogram,
        approval_rate_by_band=approval_by_band,
        city_breakdown=city_breakdown,
        override_trend=override_trend,
    )
