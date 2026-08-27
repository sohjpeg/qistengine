from __future__ import annotations

from fastapi import APIRouter

from app.ml.registry import registry
from app.schemas import ModelInfoResponse
from app.config import BACKEND_ROOT
from app.services.feature_engineering import FEATURE_ORDER

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    registry.ensure()
    st = registry.status()
    return {
        "status": "ok",
        "model_loaded": st["loaded"],
        "model_version": st["version"],
        "model_error": st["error"],
        "trained_at": st["trained_at"],
    }


@router.get("/api/v1/model/info", response_model=ModelInfoResponse)
def model_info() -> ModelInfoResponse:
    registry.ensure()
    meta = registry.metadata or {}
    fairness_summary = None
    fpath = BACKEND_ROOT.parent / "docs" / "RESPONSIBLE_AI.md"
    if fpath.exists():
        text = fpath.read_text(encoding="utf-8")
        # pull the portfolio approval-rate / four-fifths headline lines
        headline = [ln.strip() for ln in text.splitlines() if "approval rate" in ln.lower() or "four-fifths" in ln.lower()]
        fairness_summary = {"source": "docs/RESPONSIBLE_AI.md", "headlines": headline[:4]}

    return ModelInfoResponse(
        version=registry.version,
        trained_at=meta.get("trained_at"),
        feature_order=FEATURE_ORDER,
        n_features=len(FEATURE_ORDER),
        base_rate=float(meta.get("base_rate", 0.14)),
        metrics={k: float(v) for k, v in (meta.get("metrics") or {}).items()},
        decile_lift=meta.get("decile_lift", []),
        hyperparameters=meta.get("hyperparameters", {}),
        fairness_summary=fairness_summary,
    )
