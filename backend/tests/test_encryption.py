"""PII encryption at rest.

The pre-existing API test asserts the *response* is masked, which says nothing
about what lands on disk. These tests open the SQLite file directly and inspect
its bytes.
"""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine, select

from app import config
from app.models import Applicant, Application, Decision, Document
from app.security import crypto

NAME = "Zainab Testcase"
CNIC = "*****-*******-4"
PURPOSE = "Inventory-restock-sentinel"
NOTE = "officer-note-sentinel"
CONSUMER = "10066608196647"
FILENAME = "muzaffarabad-bill-sentinel.pdf"
SENTINELS = [NAME, CNIC, PURPOSE, NOTE, CONSUMER, FILENAME]


@pytest.fixture
def db(tmp_path):
    """A throwaway database, disposed so the file can be read byte-for-byte."""
    crypto.reset_cache()
    path = tmp_path / "enc.db"
    engine = create_engine(f"sqlite:///{path}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        appl = Applicant(
            full_name=NAME, cnic_masked=CNIC, phone_masked="******4242",
            city="Karachi", archetype="street_vendor", business_type="Street vending",
        )
        s.add(appl)
        s.flush()
        app = Application(applicant_id=appl.id, purpose=PURPOSE, requested_amount_pkr=50000)
        s.add(app)
        s.flush()
        s.add(Document(
            application_id=app.id, doc_type="UTILITY_BILL", filename=FILENAME,
            extraction_method="pdf_text", confidence=0.9,
            extracted_json={"consumer_number": CONSUMER, "units": 210},
        ))
        s.add(Decision(application_id=app.id, decision="APPROVE", officer_note=NOTE))
        s.commit()
    engine.dispose()
    yield path
    crypto.reset_cache()


def test_pii_is_not_plaintext_in_the_sqlite_file(db):
    raw = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    stored = [
        *raw.execute("select full_name, cnic_masked, phone_masked from applicant").fetchone(),
        raw.execute("select purpose from application").fetchone()[0],
        *raw.execute("select filename, extracted_json from document").fetchone(),
        raw.execute("select officer_note from decision").fetchone()[0],
    ]
    for value in stored:
        assert value.startswith(crypto.PREFIX), f"stored in the clear: {value!r}"
    raw.close()

    blob = db.read_bytes()
    for sentinel in SENTINELS:
        assert sentinel.encode("utf-8") not in blob, f"{sentinel!r} is readable on disk"
        assert sentinel.encode("utf-16-le") not in blob

    # Negative control: without this the test would pass even if nothing was
    # ever written, and it proves the byte scan can actually see plaintext.
    assert b"Karachi" in blob, "city should stay plaintext and be visible in the file"


def test_roundtrip_returns_plaintext_through_model_dump(db):
    engine = create_engine(f"sqlite:///{db}")
    with Session(engine) as s:
        appl = s.exec(select(Applicant)).one()
        # The detail route splats model_dump(), so decryption must be transparent.
        assert appl.model_dump()["full_name"] == NAME
        assert appl.cnic_masked == CNIC
        doc = s.exec(select(Document)).one()
        assert doc.extracted_json["consumer_number"] == CONSUMER
        assert doc.extracted_json["units"] == 210
        assert doc.filename == FILENAME
        assert s.exec(select(Application)).one().purpose == PURPOSE
        assert s.exec(select(Decision)).one().officer_note == NOTE
    engine.dispose()


def test_city_filter_still_works_in_sql(db):
    """Regression guard for the encrypted/plaintext split."""
    engine = create_engine(f"sqlite:///{db}")
    with Session(engine) as s:
        assert s.exec(select(Applicant).where(Applicant.city == "Karachi")).one().full_name == NAME
        assert s.exec(select(Applicant).where(Applicant.city == "Lahore")).all() == []
    engine.dispose()


def test_legacy_plaintext_row_is_read_back_unchanged(db):
    """A database written before this feature must keep working."""
    raw = sqlite3.connect(db)
    raw.execute(
        "insert into applicant (id, full_name, cnic_masked, phone_masked, city,"
        " archetype, business_type, dependents_count, has_fixed_premises, created_at)"
        " values ('legacy', 'Old Plaintext Name', '*****-*******-1', '******1111',"
        " 'Multan', 'small_farmer', 'Farming', 2, 0, '2026-01-01T00:00:00')"
    )
    raw.commit()
    raw.close()

    engine = create_engine(f"sqlite:///{db}")
    with Session(engine) as s:
        assert s.get(Applicant, "legacy").full_name == "Old Plaintext Name"
    engine.dispose()


def test_wrong_key_yields_a_sentinel_rather_than_crashing(db, monkeypatch):
    monkeypatch.setenv("QIST_PII_KEY", "a-completely-different-key")
    config.get_settings.cache_clear()
    crypto.reset_cache()
    try:
        engine = create_engine(f"sqlite:///{db}")
        with Session(engine) as s:
            assert s.exec(select(Applicant)).one().full_name == crypto.UNREADABLE
        engine.dispose()
    finally:
        monkeypatch.undo()
        config.get_settings.cache_clear()
        crypto.reset_cache()


def test_production_without_a_key_raises(monkeypatch):
    monkeypatch.setenv("QIST_ENV", "production")
    monkeypatch.setenv("QIST_PII_KEY", "")
    config.get_settings.cache_clear()
    crypto.reset_cache()
    try:
        with pytest.raises(RuntimeError, match="QIST_PII_KEY"):
            crypto.encrypt("anything")
    finally:
        monkeypatch.undo()
        config.get_settings.cache_clear()
        crypto.reset_cache()


def test_encrypted_values_are_non_deterministic():
    crypto.reset_cache()
    assert crypto.encrypt("same") != crypto.encrypt("same")
    assert crypto.decrypt(crypto.encrypt("same")) == "same"
