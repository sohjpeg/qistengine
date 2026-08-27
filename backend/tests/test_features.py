"""Feature contract + behavioural aggregation + fairness-by-construction checks."""
from __future__ import annotations

import numpy as np

from app.services.feature_engineering import (
    FEATURE_ORDER,
    N_FEATURES,
    POPULATION_MEDIANS,
    PROTECTED_ATTRIBUTES,
    behavioral_metrics,
    build_feature_vector,
    confidence_from_gaps,
    detect_data_gaps,
)


def test_feature_contract_is_frozen_at_26():
    assert N_FEATURES == 26
    assert len(FEATURE_ORDER) == 26
    assert len(set(FEATURE_ORDER)) == 26


def test_population_medians_cover_every_feature():
    assert set(POPULATION_MEDIANS) == set(FEATURE_ORDER)


def test_protected_attributes_are_never_features():
    for attr in PROTECTED_ATTRIBUTES:
        assert attr not in FEATURE_ORDER
    for banned in ("gender", "religion", "ethnicity", "caste", "marital_status", "load_shedding_flag"):
        assert banned not in FEATURE_ORDER


def test_build_feature_vector_orders_and_imputes():
    raw = {"utility_on_time_ratio": 0.9, "monthly_inflow_pkr": 50000}
    vec = build_feature_vector(raw)
    assert vec.shape == (26,)
    assert vec[FEATURE_ORDER.index("utility_on_time_ratio")] == 0.9
    # missing feature falls back to median
    idx = FEATURE_ORDER.index("savings_rate")
    assert vec[idx] == POPULATION_MEDIANS["savings_rate"]


def test_detect_data_gaps_flags_missing_blocks():
    only_bill = {f: 0.5 for f in FEATURE_ORDER[:5]}
    gaps = detect_data_gaps(only_bill)
    blocks = {g["block"] for g in gaps}
    assert "transaction_log" in blocks
    assert "utility_bill" not in blocks


def test_confidence_drops_with_missing_data():
    full = {f: POPULATION_MEDIANS[f] for f in FEATURE_ORDER}
    partial = {f: POPULATION_MEDIANS[f] for f in FEATURE_ORDER[:5]}
    c_full = confidence_from_gaps(detect_data_gaps(full), 12.0)
    c_partial = confidence_from_gaps(detect_data_gaps(partial), 4.0)
    assert c_full > c_partial
    assert 0.0 <= c_partial <= 1.0


def test_behavioral_metrics_in_range_and_six_axes():
    m = behavioral_metrics(dict(POPULATION_MEDIANS))
    assert set(m) == {
        "payment_discipline", "cashflow_stability", "transaction_activity",
        "savings_behavior", "business_maturity", "network_trust",
    }
    for v in m.values():
        assert 0 <= v <= 100


def test_behavioral_metrics_react_to_discipline():
    good = dict(POPULATION_MEDIANS)
    good.update(utility_on_time_ratio=0.99, utility_avg_days_late=0, utility_disconnection_events=0)
    bad = dict(POPULATION_MEDIANS)
    bad.update(utility_on_time_ratio=0.2, utility_avg_days_late=40, utility_disconnection_events=3)
    assert behavioral_metrics(good)["payment_discipline"] > behavioral_metrics(bad)["payment_discipline"]
