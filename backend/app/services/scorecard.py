"""Points-to-double-the-odds scorecard scaling.

Because the score is an affine function of log-odds, and SHAP values for a tree
model are additive in log-odds, a SHAP value converts to score points by a single
multiplication by `FACTOR`. The explanation is therefore mathematically exact,
not an approximation. See docs/SCORING_METHODOLOGY.md.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

PDO: float = 40.0  # points to double the odds
BASE_SCORE: float = 660.0
BASE_ODDS: float = 30.0  # 30:1 good:bad at BASE_SCORE

FACTOR: float = PDO / math.log(2)  # 57.7078...
OFFSET: float = BASE_SCORE - FACTOR * math.log(BASE_ODDS)

SCORE_MIN = 300
SCORE_MAX = 850

_PD_FLOOR = 1e-6
_PD_CEIL = 1.0 - 1e-6


@dataclass(frozen=True)
class Band:
    key: str
    label: str
    lo: int
    hi: int
    badge_color: str
    policy: str
    glyph: str  # Lucide icon name used by RiskBadge


BANDS: list[Band] = [
    Band("LOW", "Auto-approve", 720, 850, "emerald", "Auto-approve up to limit", "ShieldCheck"),
    Band("MEDIUM", "Manual review", 640, 719, "amber", "Manual review, reduced tenor", "AlertCircle"),
    Band("HIGH", "Guarantor required", 560, 639, "orange", "Guarantor or collateral required", "AlertTriangle"),
    Band("VERY_HIGH", "Decline", 300, 559, "rose", "Decline, offer financial-literacy referral", "XOctagon"),
]

_BAND_BY_KEY = {b.key: b for b in BANDS}


def pd_to_raw_score(pd: float) -> float:
    pd = min(_PD_CEIL, max(_PD_FLOOR, float(pd)))
    odds = (1.0 - pd) / pd
    return OFFSET + FACTOR * math.log(odds)


def pd_to_score(pd: float) -> int:
    raw = pd_to_raw_score(pd)
    return int(min(SCORE_MAX, max(SCORE_MIN, round(raw))))


def score_to_band(score: int) -> Band:
    for b in BANDS:
        if b.lo <= score <= b.hi:
            return b
    # Defensive: clip.
    return BANDS[0] if score > BANDS[0].hi else BANDS[-1]


def band(key: str) -> Band:
    return _BAND_BY_KEY[key]


def base_score_contribution() -> float:
    """The score you would get at the model's own expected value of default.

    Used by the explainer: sum(points) + this == score, exactly.
    Callers pass the SHAP expected value (log-odds of default) so this resolves
    to OFFSET + FACTOR * (-expected_value).
    """
    return BASE_SCORE
