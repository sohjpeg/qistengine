"""The frontend mirrors app/reference.py; this fails if the two drift apart.

The lists are duplicated rather than served from an endpoint because the apply
form has to keep working when the backend is asleep (NEXT_PUBLIC_DEMO_MODE).
Duplication is fine as long as something checks it.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.reference import ARCHETYPES, ARCHETYPE_LABELS, CITIES

REFERENCE_TS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "reference.ts"


def _ts_source() -> str:
    if not REFERENCE_TS.exists():  # frontend not checked out
        pytest.skip(f"{REFERENCE_TS} not present")
    return REFERENCE_TS.read_text(encoding="utf-8")


def _block(source: str, name: str) -> str:
    m = re.search(rf"export const {name}[^=]*=\s*\[(.*?)\]\s*(?:as const)?;", source, re.S)
    assert m, f"could not find `export const {name}` in reference.ts"
    return m.group(1)


def test_city_lists_match():
    found = re.findall(r'"([^"]+)"', _block(_ts_source(), "CITIES"))
    assert found == list(CITIES), "reference.ts CITIES has drifted from app/reference.py"


def test_archetype_values_and_labels_match():
    pairs = re.findall(r'\[\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\]', _block(_ts_source(), "ARCHETYPES"))
    assert [v for v, _ in pairs] == list(ARCHETYPES), "reference.ts ARCHETYPES values have drifted"
    assert {v: l for v, l in pairs} == ARCHETYPE_LABELS, "reference.ts archetype labels have drifted"


def test_new_vocabulary_is_present():
    """The values this branch added, asserted by name so a silent revert is caught."""
    for city in ("Islamabad", "Muzaffarabad", "Sargodha", "Bahawalpur", "Sukkur",
                 "Larkana", "Abbottabad", "Mardan"):
        assert city in CITIES
    assert "small_farmer" in ARCHETYPES
    assert "street_vendor" in ARCHETYPES
