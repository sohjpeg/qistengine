"""Parsing real-world wallet statements.

The fixtures are anonymised NayaPay exports. They reproduce the structural
quirks of the real thing — a preamble before the header, descriptions spanning
several physical lines inside quotes, a newline inside a TYPE cell, signed
comma-grouped amounts, "01 Jul 2026 06:11 PM" timestamps — with invented names
and account numbers. The preamble's own Total Spent / Total Income are computed
from the body rows, so they work as an oracle for the parse.
"""
from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest

from app.services.feature_engineering import TRAINING_RANGES
from app.services.transaction_parser import (
    _parse_date,
    _resolve_columns,
    parse_transaction_files,
    parse_transactions,
)

FIXTURES = Path(__file__).parent / "fixtures"
M07, M08 = FIXTURES / "nayapay_m07.csv", FIXTURES / "nayapay_m08.csv"


def _item(path: Path) -> tuple[str, bytes]:
    return path.name, path.read_bytes()


def _statement_totals(path: Path) -> tuple[float, float]:
    """Total Spent / Total Income as declared in the statement's own preamble."""
    for row in csv.reader(io.StringIO(path.read_text(encoding="utf-8"))):
        if row and row[0].strip() == "Opening Balance":
            cells = {row[i].strip(): row[i + 1] for i in range(0, len(row) - 1)}
            return (
                float(cells["Total Spent"].replace(",", "")),
                float(cells["Total Income"].replace(",", "")),
            )
    raise AssertionError("fixture has no Opening Balance summary row")


def test_multiline_quoted_description_does_not_crash():
    """The regression: header sniffing used to hand each physical line to a CSV
    parser separately, so a quoted description spanning lines raised an
    unterminated-quote error before any row was read."""
    result = parse_transactions(*_item(M07))
    assert result["row_count"] > 20
    joined = " ".join(t["counterparty"] for t in result["transactions"])
    assert "Transaction ID" in joined, "multi-line description content was truncated"


def test_totals_match_the_statement_preamble():
    """Proves the parse is correct, not merely non-crashing."""
    for path in (M07, M08):
        spent, income = _statement_totals(path)
        r = parse_transactions(*_item(path))
        inflow = sum(t["amount"] for t in r["transactions"] if t["direction"] == "credit")
        outflow = sum(t["amount"] for t in r["transactions"] if t["direction"] == "debit")
        assert inflow == pytest.approx(income, abs=0.01), path.name
        assert outflow == pytest.approx(spent, abs=0.01), path.name


def test_bill_payment_via_1link_is_classified_as_utility():
    """TYPE carries the payment rail and used to be discarded; "1BILL" also has
    no word boundary before "bill"."""
    r = parse_transactions(*_item(M08))
    bills = [t for t in r["transactions"] if "1BILL" in t["counterparty"]]
    assert bills, "fixture should contain a 1BILL row"
    assert bills[0]["category"] == "OUTFLOW_UTILITY"
    assert any(m["utility_paid_on_time"] for m in r["monthly_series"])


def test_pos_purchase_is_not_read_as_merchant_income():
    r = parse_transactions(*_item(M08))
    pos = [t for t in r["transactions"] if "METRO CASH" in t["counterparty"]]
    assert pos and pos[0]["direction"] == "debit"


def test_reversal_is_not_counted_as_income():
    r = parse_transactions(*_item(M08))
    reversals = [t for t in r["transactions"] if t["category"] == "REVERSAL"]
    assert reversals, "fixture should contain a reversal"
    _, income = _statement_totals(M08)
    # The statement's own Total Income includes the reversal; ours must not.
    assert r["monthly_series"][0]["inflow_pkr"] < income


def test_expense_to_income_ratio_is_plausible_not_zero():
    """It used to count only keyword-matched essentials, so a wallet export full
    of bare transfers scored 0.0 — the single most favourable value."""
    r = parse_transaction_files([_item(M07), _item(M08)])
    ratio = r["derived_features"]["expense_to_income_ratio"]
    lo, hi = TRAINING_RANGES["expense_to_income_ratio"]
    assert lo <= ratio <= hi
    assert ratio > 0.3


def test_single_month_omits_volatility_and_trend():
    """One month cannot evidence either; they must be absent so the caller
    imputes a median and records a data gap, rather than silently receiving the
    best possible value."""
    r = parse_transactions(*_item(M07))
    assert r["months_observed"] == 1
    assert "cashflow_volatility" not in r["derived_features"]
    assert "income_trend_slope" not in r["derived_features"]


def test_two_files_aggregate_into_one_ledger():
    r = parse_transaction_files([_item(M07), _item(M08)])
    assert r["months_observed"] == 2
    assert [m["month"] for m in r["monthly_series"]] == ["2026-07", "2026-08"]
    assert r["derived_features"]["cashflow_volatility"] > 0
    assert "income_trend_slope" in r["derived_features"]
    single = parse_transactions(*_item(M07))
    assert r["row_count"] > single["row_count"]


def test_duplicate_upload_is_deduped():
    once = parse_transaction_files([_item(M07), _item(M08)])
    twice = parse_transaction_files([_item(M07), _item(M08), _item(M08)])
    assert twice["row_count"] == once["row_count"]
    assert twice["months_observed"] == once["months_observed"]


def test_one_unreadable_file_does_not_lose_the_others():
    r = parse_transaction_files([_item(M07), ("junk.csv", b"alpha,beta\n1,2\n")])
    assert r["row_count"] == parse_transactions(*_item(M07))["row_count"]
    assert r["skipped_files"] and "junk.csv" in r["skipped_files"][0]


def test_all_unreadable_raises():
    with pytest.raises(ValueError):
        parse_transaction_files([("junk.csv", b"alpha,beta\n1,2\n")])


def test_derived_features_stay_within_the_training_ranges():
    """A real deficit month can produce a net_cashflow_ratio far outside the
    range the model was fitted on; scoring that is extrapolation, not a score."""
    r = parse_transaction_files([_item(M07), _item(M08)])
    for name, value in r["derived_features"].items():
        if name in TRAINING_RANGES:
            lo, hi = TRAINING_RANGES[name]
            assert lo <= value <= hi, f"{name}={value} outside {(lo, hi)}"


def test_iso_dates_are_not_read_day_first():
    assert _parse_date("2026-07-01").month == 7
    assert _parse_date("01 Jul 2026 06:11 PM").month == 7
    assert _parse_date("03-07-2026").day == 3  # day-first for local formats


def test_credit_alias_does_not_capture_the_description_column():
    """"cr" is a substring of "description"; the loose alias match used to read
    amounts out of the narrative column."""
    cols = _resolve_columns(["TIMESTAMP", "TYPE", "DESCRIPTION", "AMOUNT", "BALANCE"])
    assert cols["credit"] is None
    assert cols["amount"] == "AMOUNT"
    assert cols["date"] == "TIMESTAMP"


def test_single_character_headers_do_not_fabricate_transactions():
    """A 1-2 character header is a substring of nearly every alias."""
    assert not any(_resolve_columns(["a", "b"]).values())


def test_shipped_sample_ledgers_still_parse():
    """The synthetic demo ledgers must keep working unchanged."""
    samples = sorted((Path(__file__).parents[1] / "data" / "samples").glob("*ledger.csv"))
    assert len(samples) == 6
    for path in samples:
        r = parse_transactions(path.name, path.read_bytes())
        assert r["row_count"] > 0 and r["months_observed"] >= 1, path.name
