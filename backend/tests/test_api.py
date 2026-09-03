"""API contract tests against an in-process app with a temp database."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = BACKEND_ROOT / "tests" / "fixtures" / "sample_score_request.json"


@pytest.fixture(scope="module")
def client():
    tmp = tempfile.mkdtemp()
    os.environ["QIST_DATABASE_URL"] = f"sqlite:///{Path(tmp) / 'test.db'}"
    # rebuild settings + engine with the temp DB
    import app.config as config

    config.get_settings.cache_clear()
    config.settings = config.get_settings()
    import importlib

    import app.database as database

    importlib.reload(database)
    import app.main as main

    importlib.reload(main)

    with TestClient(main.app) as c:
        yield c


def test_health_reports_model_status(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["model_loaded"] is True
    assert body["model_version"]


def test_model_info_lists_26_features(client):
    r = client.get("/api/v1/model/info")
    assert r.status_code == 200
    body = r.json()
    assert body["n_features"] == 26
    assert len(body["feature_order"]) == 26
    assert body["metrics"]["roc_auc"] >= 0.78


def test_score_endpoint_returns_valid_contract(client):
    payload = json.loads(FIXTURE.read_text())
    r = client.post("/api/v1/score", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert 300 <= body["score"] <= 850
    assert body["risk_band"] in ("LOW", "MEDIUM", "HIGH", "VERY_HIGH")
    assert 0.0 <= body["probability_of_default"] <= 1.0
    assert body["qist_limit"]["safe_installment_pkr"] % 500 == 0
    assert len(body["behavioral_metrics"]) == 6
    assert body["disclaimer"]
    # ledger additivity
    total = body["base_contribution"] + sum(c["impact_points"] for c in body["ledger_lines"])
    assert abs(total - body["score"]) <= 3  # integer points, so allow rounding slack
    # what-if support: the full 26-feature vector is echoed back
    assert len(body["features_used"]) == 26


def test_what_if_rescore_reacts_to_a_lever(client):
    """Powers the SensitivityPanel: re-scoring with a worse utility ratio drops
    the score, and a bigger disposable income raises the safe installment."""
    payload = json.loads(FIXTURE.read_text())
    base = client.post("/api/v1/score", json=payload).json()
    feats = dict(base["features_used"])

    worse = {**feats, "utility_on_time_ratio": 0.15, "utility_avg_days_late": 40}
    r_worse = client.post(
        "/api/v1/score", json={"features": worse, "archetype_hint": "kiryana_merchant"}
    ).json()
    assert r_worse["score"] < base["score"]

    richer = {**feats, "monthly_inflow_pkr": feats["monthly_inflow_pkr"] * 1.6}
    r_rich = client.post(
        "/api/v1/score", json={"features": richer, "archetype_hint": "kiryana_merchant"}
    ).json()
    if base["qist_limit"]["eligible"] and r_rich["qist_limit"]["eligible"]:
        assert r_rich["qist_limit"]["safe_installment_pkr"] >= base["qist_limit"]["safe_installment_pkr"]


def test_score_with_partial_data_populates_data_gaps(client):
    r = client.post("/api/v1/score", json={"features": {"utility_on_time_ratio": 0.8, "utility_months_observed": 6}})
    assert r.status_code == 200
    body = r.json()
    assert body["data_gaps"]
    assert body["confidence"] < 1.0


def test_mock_profiles_span_at_least_three_bands(client):
    r = client.get("/api/v1/mock/profiles")
    assert r.status_code == 200
    profiles = r.json()
    assert len(profiles) == 6
    bands = set()
    for p in profiles:
        sr = client.post(
            "/api/v1/score",
            json={"features": p["features"], "archetype_hint": p["archetype"]},
        ).json()
        bands.add(sr["risk_band"])
    assert len(bands) >= 3


def test_application_lifecycle_create_list_decide(client):
    payload = json.loads(FIXTURE.read_text())
    create = client.post(
        "/api/v1/applications",
        json={
            "applicant": {
                "full_name": "Test Merchant",
                "cnic": "42101-1234567-8",
                "phone": "0300-1234567",
                "city": "Karachi",
                "archetype": "kiryana_merchant",
                "business_type": "Grocery",
                "dependents_count": 3,
                "has_fixed_premises": True,
            },
            "requested_amount_pkr": 60000,
            "purpose": "Inventory",
            "features": payload["features"],
        },
    )
    assert create.status_code == 201, create.text
    detail = create.json()
    app_id = detail["id"]
    assert detail["applicant"]["cnic_masked"].startswith("*****-*******-")
    assert "1234567" not in json.dumps(detail)  # raw CNIC never stored
    assert detail["score_result"]["score"]

    lst = client.get("/api/v1/applications")
    assert lst.status_code == 200
    assert any(i["id"] == app_id for i in lst.json()["items"])

    dec = client.patch(
        f"/api/v1/applications/{app_id}/decision",
        json={"decision": "APPROVE", "approved_amount_pkr": 50000, "officer_note": "ok"},
    )
    assert dec.status_code == 200
    assert dec.json()["status"] == "APPROVED"


def test_override_requires_justification(client):
    create = client.post(
        "/api/v1/applications",
        json={
            "applicant": {
                "full_name": "Risky Applicant",
                "cnic": "42101-9999999-9",
                "phone": "0300-9999999",
                "city": "Multan",
                "archetype": "daily_wage_worker",
                "business_type": "Labour",
            },
            "requested_amount_pkr": 40000,
            "purpose": "Buffer",
            "features": {
                "utility_on_time_ratio": 0.3, "expense_to_income_ratio": 1.1,
                "cashflow_volatility": 0.7, "balance_floor_ratio": 0.0,
                "monthly_inflow_pkr": 25000, "monthly_outflow_pkr": 25000,
                "utility_months_observed": 5,
            },
        },
    ).json()
    app_id = create["id"]
    if create["score_result"]["risk_band"] != "VERY_HIGH":
        pytest.skip("profile did not land VERY_HIGH")
    bad = client.patch(
        f"/api/v1/applications/{app_id}/decision",
        json={"decision": "APPROVE", "approved_installment_pkr": 5000},
    )
    assert bad.status_code == 422
    good = client.patch(
        f"/api/v1/applications/{app_id}/decision",
        json={"decision": "APPROVE", "approved_installment_pkr": 5000, "justification": "Long-standing customer, branch manager approved."},
    )
    assert good.status_code == 200
    assert good.json()["decision"]["override_flag"] is True


def test_metrics_endpoint_shape(client):
    r = client.get("/api/v1/metrics")
    assert r.status_code == 200
    body = r.json()
    for key in (
        "applications_total", "approval_rate", "mean_score",
        "portfolio_expected_loss_pkr", "override_rate", "band_distribution",
        "score_histogram", "city_breakdown",
    ):
        assert key in body


def test_parse_transactions_csv(client):
    csv = "date,amount,type,description,balance\n01-06-2025,15000,credit,QR sale customer,20000\n03-06-2025,-2000,debit,K-Electric bijli bill,18000\n05-06-2025,-500,debit,easyload topup,17500\n10-07-2025,16000,credit,QR sale,21000\n"
    r = client.post(
        "/api/v1/parse-transactions",
        files={"file": ("ledger.csv", csv, "text/csv")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["row_count"] == 4
    assert body["months_observed"] == 2
    assert "monthly_inflow_pkr" in body["derived_features"]


def test_parse_bill_fallback_is_labelled(client):
    r = client.post(
        "/api/v1/parse-bill",
        files={"file": ("random.png", b"not a real image", "image/png")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["extraction_method"] == "simulated"
    assert body["confidence"] == 0.0
