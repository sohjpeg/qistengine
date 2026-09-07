"""SQLModel ORM tables for QistEngine persistence.

Sensitive identifiers (CNIC, phone) are stored masked only. The raw values never
reach the database; masking happens at the schema boundary before persistence.

Identifying columns are additionally encrypted at rest with AES-256-GCM (see
`app.security.crypto`): applicant name, masked CNIC/phone, loan purpose,
document filename, extracted bill fields (which carry a utility consumer
number), and officer notes.

Left in plaintext on purpose, because they are queried in SQL rather than merely
displayed: `Applicant.city` (the queue filters on it), `Application.status` and
`ScoreResult.risk_band` (both indexed and filtered), all primary/foreign keys and
timestamps, and every `ScoreResult.*_json` column — those hold pseudonymous
numeric aggregates and SHAP explanations, not identifiers, and keeping them
readable is what makes the demo database inspectable.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel

from app.security.crypto import EncryptedJSON, EncryptedString


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Applicant(SQLModel, table=True):
    __tablename__ = "applicant"

    id: str = Field(default_factory=_uuid, primary_key=True)
    full_name: str = Field(sa_column=Column(EncryptedString, nullable=False))
    cnic_masked: str = Field(
        sa_column=Column(EncryptedString, nullable=False),
        description="Format: *****-*******-*, never a real CNIC",
    )
    phone_masked: str = Field(sa_column=Column(EncryptedString, nullable=False))
    city: str  # plaintext: filtered in SQL by the underwriting queue
    archetype: str
    business_type: str
    dependents_count: int = 0
    has_fixed_premises: bool = False
    created_at: datetime = Field(default_factory=_now)


class Application(SQLModel, table=True):
    __tablename__ = "application"

    id: str = Field(default_factory=_uuid, primary_key=True)
    applicant_id: str = Field(foreign_key="applicant.id", index=True)
    status: str = Field(default="PENDING", index=True)  # PENDING|SCORED|APPROVED|REJECTED|NEEDS_INFO
    requested_amount_pkr: float = 0.0
    purpose: str = Field(default="", sa_column=Column(EncryptedString))
    submitted_at: datetime = Field(default_factory=_now)
    decided_at: datetime | None = None
    decided_by: str | None = None


class Document(SQLModel, table=True):
    __tablename__ = "document"

    id: str = Field(default_factory=_uuid, primary_key=True)
    application_id: str = Field(foreign_key="application.id", index=True)
    doc_type: str  # UTILITY_BILL | TRANSACTION_LOG
    filename: str = Field(sa_column=Column(EncryptedString, nullable=False))
    extraction_method: str
    confidence: float
    # Carries the utility consumer number, so encrypted rather than plain JSON.
    extracted_json: dict = Field(default_factory=dict, sa_column=Column(EncryptedJSON))
    uploaded_at: datetime = Field(default_factory=_now)


class ScoreResult(SQLModel, table=True):
    __tablename__ = "score_result"
    model_config = {"protected_namespaces": ()}  # allow the `model_version` column

    id: str = Field(default_factory=_uuid, primary_key=True)
    application_id: str = Field(foreign_key="application.id", index=True)
    score: int
    probability_of_default: float
    risk_band: str = Field(index=True)
    model_version: str
    features_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    reason_codes_json: list = Field(default_factory=list, sa_column=Column(JSON))
    qist_limit_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    behavioral_metrics_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    monthly_series_json: list = Field(default_factory=list, sa_column=Column(JSON))
    data_gaps_json: list = Field(default_factory=list, sa_column=Column(JSON))
    confidence: float = 1.0
    scored_at: datetime = Field(default_factory=_now)


class Decision(SQLModel, table=True):
    __tablename__ = "decision"

    id: str = Field(default_factory=_uuid, primary_key=True)
    application_id: str = Field(foreign_key="application.id", index=True)
    decision: str  # APPROVE | APPROVE_MODIFIED | REQUEST_INFO | REJECT
    approved_amount_pkr: float | None = None
    approved_installment_pkr: float | None = None
    tenor_months: int | None = None
    officer_note: str = Field(default="", sa_column=Column(EncryptedString))
    override_flag: bool = False
    created_at: datetime = Field(default_factory=_now)
