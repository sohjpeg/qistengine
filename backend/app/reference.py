"""Product vocabulary: the cities and livelihoods an applicant can be recorded as.

Single source of truth for values that used to be duplicated across the
synthetic-data generator, the seeder, the sample-file builder and two frontend
dropdowns. `frontend/src/lib/reference.ts` mirrors this file and is kept honest
by `tests/test_reference_sync.py`.

Neither city nor livelihood is a model feature — the scorecard reads 26
behavioural signals and never sees either (see `feature_engineering.FEATURE_ORDER`
and `PROTECTED_ATTRIBUTES`). They are recorded for display, for the underwriting
queue's filters, and as fairness-audit axes.

Note the distinction from `scripts/generate_synthetic_data.TRAINING_CITIES` /
`TRAINING_ARCHETYPES`: those are the frozen vocabulary the shipped model was
trained on, and are deliberately a subset of what is listed here. Because
neither attribute is a feature, an applicant in a city or livelihood outside the
training vocabulary still scores normally.
"""
from __future__ import annotations

from typing import NamedTuple


class CityInfo(NamedTuple):
    tier: int          # 1 = largest metros, 3 = smaller cities / regions
    disco: str         # electricity distribution company
    gas: str           # SSGC (south) or SNGPL (north)


# Ordered: iteration order is the order shown in the UI dropdowns.
CITY_META: dict[str, CityInfo] = {
    "Karachi":      CityInfo(1, "K-Electric", "SSGC"),
    "Lahore":       CityInfo(1, "LESCO", "SNGPL"),
    "Islamabad":    CityInfo(1, "IESCO", "SNGPL"),
    "Faisalabad":   CityInfo(2, "FESCO", "SNGPL"),
    "Rawalpindi":   CityInfo(2, "IESCO", "SNGPL"),
    "Multan":       CityInfo(2, "MEPCO", "SNGPL"),
    "Peshawar":     CityInfo(2, "PESCO", "SNGPL"),
    "Hyderabad":    CityInfo(2, "HESCO", "SSGC"),
    "Gujranwala":   CityInfo(3, "GEPCO", "SNGPL"),
    "Sialkot":      CityInfo(3, "GEPCO", "SNGPL"),
    "Quetta":       CityInfo(3, "QESCO", "SSGC"),
    "Sargodha":     CityInfo(3, "FESCO", "SNGPL"),
    "Bahawalpur":   CityInfo(3, "MEPCO", "SNGPL"),
    "Sukkur":       CityInfo(3, "SEPCO", "SSGC"),
    "Larkana":      CityInfo(3, "SEPCO", "SSGC"),
    "Abbottabad":   CityInfo(3, "PESCO", "SNGPL"),
    "Mardan":       CityInfo(3, "PESCO", "SNGPL"),
    "Muzaffarabad": CityInfo(3, "AJKESCO", "SNGPL"),  # Azad Jammu & Kashmir
}

CITIES: tuple[str, ...] = tuple(CITY_META)
CITY_TIER: dict[str, int] = {c: m.tier for c, m in CITY_META.items()}
ELECTRICITY_BY_CITY: dict[str, str] = {c: m.disco for c, m in CITY_META.items()}
GAS_BY_CITY: dict[str, str] = {c: m.gas for c, m in CITY_META.items()}


class ArchetypeInfo(NamedTuple):
    label: str          # human-readable, for dropdowns and detail pages
    business_type: str  # default business description on a seeded applicant
    slug: str           # short token used in sample-file names


ARCHETYPE_META: dict[str, ArchetypeInfo] = {
    "kiryana_merchant":    ArchetypeInfo("Kiryana / grocery merchant", "Neighbourhood grocery", "kiryana"),
    "daily_wage_worker":   ArchetypeInfo("Daily-wage worker", "Construction & transport labour", "dailywage"),
    "home_based_producer": ArchetypeInfo("Home-based producer", "Home-based production", "homebased"),
    "ride_hailing_driver": ArchetypeInfo("Ride-hailing driver", "Ride-hailing driver", "ridehailing"),
    "small_farmer":        ArchetypeInfo("Small farmer", "Smallholder farming", "farmer"),
    "street_vendor":       ArchetypeInfo("Street vendor / thela", "Street vending & pushcart", "vendor"),
}

ARCHETYPES: tuple[str, ...] = tuple(ARCHETYPE_META)
ARCHETYPE_LABELS: dict[str, str] = {a: m.label for a, m in ARCHETYPE_META.items()}
ARCHETYPE_BUSINESS_TYPE: dict[str, str] = {a: m.business_type for a, m in ARCHETYPE_META.items()}
ARCHETYPE_SLUG: dict[str, str] = {a: m.slug for a, m in ARCHETYPE_META.items()}


def archetype_label(value: str) -> str:
    """Human-readable livelihood, falling back to de-slugified text."""
    return ARCHETYPE_LABELS.get(value) or value.replace("_", " ").capitalize()


assert len(set(ARCHETYPE_SLUG.values())) == len(ARCHETYPE_SLUG), "sample-file slugs must be unique"
