"""Pydantic v2 request/response contracts. frontend/src/lib/types.ts mirrors these."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel as _BaseModel, ConfigDict, Field, field_validator

DISCLAIMER = "Demonstration model trained on synthetic data. Not a regulated credit decision."


class BaseModel(_BaseModel):
    """Project base: disables the `model_` protected namespace so fields like
    `model_version` / `model_loaded` are allowed."""

    model_config = ConfigDict(protected_namespaces=())

RiskBand = Literal["LOW", "MEDIUM", "HIGH", "VERY_HIGH"]
ApplicationStatus = Literal["PENDING", "SCORED", "APPROVED", "REJECTED", "NEEDS_INFO"]
DecisionType = Literal["APPROVE", "APPROVE_MODIFIED", "REQUEST_INFO", "REJECT"]


# --------------------------------------------------------------------------- #
# Health / model info
# --------------------------------------------------------------------------- #
class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_version: str | None
    model_error: str | None = None
    trained_at: str | None = None


class ModelInfoResponse(BaseModel):
    version: str
    trained_at: str | None
    feature_order: list[str]
    n_features: int
    base_rate: float
    metrics: dict[str, float]
    decile_lift: list[dict[str, Any]] = Field(default_factory=list)
    hyperparameters: dict[str, Any] = Field(default_factory=dict)
    fairness_summary: dict[str, Any] | None = None


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #
class MonthlyPoint(BaseModel):
    month: str
    inflow_pkr: float
    outflow_pkr: float
    utility_paid_on_time: bool


class QistBreakdown(BaseModel):
    disposable_income_pkr: float
    dsr_cap: float
    volatility_haircut: float
    depth_confidence: float
    consistency_bonus: float


class QistLimit(BaseModel):
    eligible: bool
    reason: str | None = None
    safe_installment_pkr: int
    principal_pkr: int
    tenor_months: int
    flat_markup_monthly: float
    total_repayable_pkr: int
    breakdown: QistBreakdown


class ReasonCode(BaseModel):
    feature: str
    impact_points: int
    direction: Literal["positive", "negative"]
    label_en: str
    label_ur: str
    category: str


class BehavioralMetrics(BaseModel):
    payment_discipline: int
    cashflow_stability: int
    transaction_activity: int
    savings_behavior: int
    business_maturity: int
    network_trust: int


class DataGap(BaseModel):
    block: str
    detail: str


class ScoreRequest(BaseModel):
    """Raw signals or pre-extracted features. Anything omitted is imputed at
    population medians and reported in `data_gaps`."""

    applicant_id: str | None = None
    features: dict[str, float] | None = None
    # Optional raw blocks the caller can send instead of pre-computed features.
    bill_fields: dict[str, Any] | None = None
    transaction_aggregates: dict[str, Any] | None = None
    archetype_hint: str | None = None
    tenor_months: int | None = None

    @field_validator("tenor_months")
    @classmethod
    def _valid_tenor(cls, v: int | None) -> int | None:
        if v is not None and v not in (3, 6, 9, 12):
            raise ValueError("tenor_months must be one of 3, 6, 9, 12")
        return v


class ScoreResponse(BaseModel):
    application_id: str | None
    score: int
    probability_of_default: float
    risk_band: RiskBand
    band_label: str
    confidence: float
    qist_limit: QistLimit
    reason_codes: list[ReasonCode]
    ledger_lines: list[ReasonCode]
    base_contribution: float
    adverse_action_codes: list[str]
    behavioral_metrics: BehavioralMetrics
    portfolio_median_metrics: BehavioralMetrics
    monthly_series: list[MonthlyPoint]
    data_gaps: list[DataGap]
    features_used: dict[str, float] = Field(default_factory=dict)
    archetype_hint: str | None = None
    model_version: str
    scored_at: str
    disclaimer: str = DISCLAIMER


# --------------------------------------------------------------------------- #
# Ingestion
# --------------------------------------------------------------------------- #
class ExtractedField(BaseModel):
    name: str
    value: Any | None
    confidence: float


class ParseBillResponse(BaseModel):
    filename: str
    doc_type: Literal["UTILITY_BILL"] = "UTILITY_BILL"
    extraction_method: Literal["pdf_text", "tesseract", "simulated"]
    confidence: float
    fields: list[ExtractedField]
    derived_features: dict[str, float]
    disclaimer: str = DISCLAIMER


class NormalisedTxn(BaseModel):
    date: str
    amount: float
    direction: Literal["credit", "debit"]
    counterparty: str
    balance: float | None
    channel: str | None
    category: str


class ParseTransactionsResponse(BaseModel):
    filename: str
    doc_type: Literal["TRANSACTION_LOG"] = "TRANSACTION_LOG"
    row_count: int
    months_observed: int
    transactions: list[NormalisedTxn]
    derived_features: dict[str, float]
    monthly_series: list[MonthlyPoint]
    disclaimer: str = DISCLAIMER


# --------------------------------------------------------------------------- #
# Applications
# --------------------------------------------------------------------------- #
class ApplicantIn(BaseModel):
    full_name: str
    cnic: str = Field(description="Raw CNIC; masked before storage, never persisted raw")
    phone: str
    city: str
    archetype: str
    business_type: str
    dependents_count: int = 0
    has_fixed_premises: bool = False


class ApplicationCreate(BaseModel):
    applicant: ApplicantIn
    requested_amount_pkr: float
    purpose: str
    features: dict[str, float] | None = None
    bill_fields: dict[str, Any] | None = None
    transaction_aggregates: dict[str, Any] | None = None
    monthly_series: list[MonthlyPoint] | None = None
    tenor_months: int | None = None


class ApplicantOut(BaseModel):
    id: str
    full_name: str
    cnic_masked: str
    phone_masked: str
    city: str
    archetype: str
    business_type: str
    dependents_count: int
    has_fixed_premises: bool
    created_at: datetime


class DocumentOut(BaseModel):
    id: str
    doc_type: str
    filename: str
    extraction_method: str
    confidence: float
    extracted_json: dict[str, Any]
    uploaded_at: datetime


class DecisionOut(BaseModel):
    id: str
    decision: str
    approved_amount_pkr: float | None
    approved_installment_pkr: float | None
    tenor_months: int | None
    officer_note: str
    override_flag: bool
    created_at: datetime


class ApplicationSummary(BaseModel):
    id: str
    applicant_name: str
    city: str
    archetype: str
    status: ApplicationStatus
    requested_amount_pkr: float
    score: int | None
    risk_band: RiskBand | None
    safe_installment_pkr: int | None
    principal_pkr: int | None
    submitted_at: datetime
    decided_at: datetime | None
    override_flag: bool


class ApplicationDetail(BaseModel):
    id: str
    status: ApplicationStatus
    requested_amount_pkr: float
    purpose: str
    submitted_at: datetime
    decided_at: datetime | None
    decided_by: str | None
    applicant: ApplicantOut
    documents: list[DocumentOut]
    score_result: ScoreResponse | None
    decision: DecisionOut | None


class PaginatedApplications(BaseModel):
    items: list[ApplicationSummary]
    total: int
    page: int
    page_size: int


class DecisionCreate(BaseModel):
    decision: DecisionType
    approved_amount_pkr: float | None = None
    approved_installment_pkr: float | None = None
    tenor_months: int | None = None
    officer_note: str = ""
    decided_by: str = "underwriter"
    justification: str | None = None  # required by the client for overrides


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
class MetricsResponse(BaseModel):
    applications_total: int
    applications_today: int
    approval_rate: float
    mean_score: float
    portfolio_expected_loss_pkr: float
    override_rate: float
    band_distribution: dict[str, int]
    score_histogram: list[dict[str, Any]]
    approval_rate_by_band: dict[str, float]
    city_breakdown: list[dict[str, Any]]
    override_trend: list[dict[str, Any]]
    disclaimer: str = DISCLAIMER


class MockProfile(BaseModel):
    id: str
    display_name: str
    headline: str
    city: str
    archetype: str
    business_type: str
    requested_amount_pkr: float
    purpose: str
    applicant: ApplicantIn
    features: dict[str, float]
    bill_fields: dict[str, Any]
    monthly_series: list[MonthlyPoint]
    expected_band: RiskBand
