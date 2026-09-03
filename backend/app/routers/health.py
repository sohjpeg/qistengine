from __future__ import annotations

import json

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
    fpath = BACKEND_ROOT / "data" / "processed" / "fairness_summary.json"
    if fpath.exists():
        try:
            fairness_summary = json.loads(fpath.read_text(encoding="utf-8"))
            fairness_summary["source"] = "docs/RESPONSIBLE_AI.md"
        except (json.JSONDecodeError, OSError):
            fairness_summary = None

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
