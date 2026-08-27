"""Scorecard scaling + the exact SHAP-to-points additivity property."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from app.ml.registry import registry
from app.services.explainer import explain
from app.services.feature_engineering import FEATURE_ORDER
from app.services.scorecard import (
    BANDS,
    FACTOR,
    OFFSET,
    PDO,
    pd_to_score,
    score_to_band,
)


def test_factor_and_offset_match_spec():
    assert math.isclose(FACTOR, 40.0 / math.log(2), rel_tol=1e-9)
    assert math.isclose(OFFSET, 660.0 - FACTOR * math.log(30.0), rel_tol=1e-9)
    assert PDO == 40.0


def test_score_is_monotone_decreasing_in_pd():
    pds = [0.01, 0.05, 0.1, 0.2, 0.4, 0.8]
    scores = [pd_to_score(p) for p in pds]
    assert scores == sorted(scores, reverse=True)
    for s in scores:
        assert 300 <= s <= 850


def test_bands_are_contiguous_and_cover_full_range():
    ordered = sorted(BANDS, key=lambda b: b.lo)
    assert ordered[0].lo == 300
    assert ordered[-1].hi == 850
    for a, b in zip(ordered, ordered[1:]):
        assert b.lo == a.hi + 1


def test_score_to_band_examples():
    assert score_to_band(800).key == "LOW"
    assert score_to_band(700).key == "MEDIUM"
    assert score_to_band(600).key == "HIGH"
    assert score_to_band(400).key == "VERY_HIGH"


def _mid_risk_row() -> dict:
    from app.config import BACKEND_ROOT

    df = pd.read_csv(BACKEND_ROOT / "data" / "raw" / "synthetic_profiles.csv")
    # pick a profile near the portfolio's median predicted risk
    row = df.sort_values("pd_true").iloc[len(df) // 2]
    return {f: float(row[f]) for f in FEATURE_ORDER}


def test_shap_points_sum_to_score_within_two_points():
    registry.load()
    assert registry.loaded, registry.error
    raw = _mid_risk_row()
    from app.services.feature_engineering import build_feature_vector

    vec = build_feature_vector(raw)
    shap_vals = registry.shap_values(vec)
    margin = registry.score_margin(shap_vals)
    pd_for_score = 1.0 / (1.0 + math.exp(-margin))
    score = pd_to_score(pd_for_score)

    expl = explain(shap_vals, raw, registry.expected_value)
    total = expl["base_contribution"] + sum(
        c["impact_points_exact"] for c in expl["all_contributions"]
    )
    assert abs(total - score) <= 2.0, f"ledger {total:.2f} vs score {score}"


def test_reason_codes_have_bilingual_labels():
    registry.load()
    raw = _mid_risk_row()
    from app.services.feature_engineering import build_feature_vector

    shap_vals = registry.shap_values(build_feature_vector(raw))
    expl = explain(shap_vals, raw, registry.expected_value)
    assert expl["reason_codes"]
    for rc in expl["reason_codes"]:
        assert rc["label_en"] and rc["label_ur"]
        assert rc["label_en"] != rc["label_ur"]
        assert rc["category"]
