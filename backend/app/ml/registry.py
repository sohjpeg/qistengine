"""Model artifact registry.

Loads the calibrated LightGBM model, the StandardScaler, the SHAP TreeExplainer,
and metadata.json from QIST_MODEL_DIR. Loading is lazy and defensive: a missing
artifact sets `loaded=False` and `error`, so /health can report status instead of
the process refusing to start.
"""
from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any

import numpy as np

from app.config import settings
from app.services.feature_engineering import FEATURE_ORDER

_DEFAULT_VERSION = "qistengine-scorecard-v1.0.0"


class ModelRegistry:
    def __init__(self, model_dir: Path) -> None:
        self.model_dir = model_dir
        self.model: Any = None
        self.scaler: Any = None
        self.explainer: Any = None
        self.metadata: dict[str, Any] = {}
        self.loaded: bool = False
        self.error: str | None = None
        self._lock = Lock()
        self._tried = False

    # -- loading -----------------------------------------------------------
    def load(self, force: bool = False) -> None:
        with self._lock:
            if self.loaded and not force:
                return
            self._tried = True
            try:
                import joblib

                model_p = self.model_dir / "model.pkl"
                scaler_p = self.model_dir / "scaler.pkl"
                explainer_p = self.model_dir / "explainer.pkl"
                meta_p = self.model_dir / "metadata.json"

                missing = [p.name for p in (model_p, scaler_p, explainer_p, meta_p) if not p.exists()]
                if missing:
                    raise FileNotFoundError(
                        "Missing model artifacts: "
                        + ", ".join(missing)
                        + ". Run: python scripts/train_model.py"
                    )

                self.model = joblib.load(model_p)
                self.scaler = joblib.load(scaler_p)
                self.explainer = joblib.load(explainer_p)
                self.metadata = json.loads(meta_p.read_text(encoding="utf-8"))

                meta_order = self.metadata.get("feature_order")
                if meta_order and list(meta_order) != list(FEATURE_ORDER):
                    raise ValueError("metadata.json feature_order does not match FEATURE_ORDER")

                self.loaded = True
                self.error = None
            except Exception as exc:  # noqa: BLE001 - report, don't crash
                self.loaded = False
                self.error = str(exc)

    def ensure(self) -> None:
        if not self.loaded and (not self._tried or self.error is None):
            self.load()
        if not self.loaded and self.error and not self._tried:
            self.load()

    # -- inference -------------------------------------------------------
    def _require(self) -> None:
        if not self.loaded:
            self.load()
        if not self.loaded:
            raise RuntimeError(self.error or "Model artifacts not loaded")

    @property
    def version(self) -> str:
        return self.metadata.get("version", _DEFAULT_VERSION)

    @property
    def expected_value(self) -> float:
        return float(self.metadata.get("shap_expected_value", 0.0))

    @property
    def base_rate(self) -> float:
        return float(self.metadata.get("base_rate", 0.14))

    def scale(self, vec: np.ndarray) -> np.ndarray:
        self._require()
        arr = np.asarray(vec, dtype=np.float64).reshape(1, -1)
        return self.scaler.transform(arr)

    def predict_pd(self, vec: np.ndarray) -> float:
        """Calibrated probability of default (isotonic). Used for display and the
        Qist Limit."""
        self._require()
        scaled = self.scale(vec)
        proba = self.model.predict_proba(scaled)[0, 1]
        return float(proba)

    def score_margin(self, shap_vals: np.ndarray) -> float:
        """Uncalibrated LightGBM log-odds of default, reconstructed from SHAP
        additivity: margin == expected_value + sum(shap). The credit score is an
        affine transform of this, so the reason-code points sum to the score
        exactly."""
        return float(self.expected_value) + float(np.asarray(shap_vals).sum())

    def shap_values(self, vec: np.ndarray) -> np.ndarray:
        """Per-feature SHAP values in log-odds space for the (scaled) row."""
        self._require()
        scaled = self.scale(vec)
        raw = self.explainer.shap_values(scaled)
        # shap may return list [class0, class1] for binary; take positive class.
        if isinstance(raw, list):
            raw = raw[-1]
        arr = np.asarray(raw, dtype=np.float64)
        if arr.ndim == 3:  # (n, features, classes)
            arr = arr[0, :, -1]
        elif arr.ndim == 2:
            arr = arr[0]
        return arr.reshape(-1)

    def status(self) -> dict[str, Any]:
        return {
            "loaded": self.loaded,
            "error": self.error,
            "version": self.version if self.loaded else None,
            "trained_at": self.metadata.get("trained_at") if self.loaded else None,
            "metrics": self.metadata.get("metrics") if self.loaded else None,
        }


registry = ModelRegistry(settings.model_dir_path)
