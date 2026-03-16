"""Shared color-coding and formatting for styled DataFrames.

TZ rules (sections 5.1, 7.5, 10.4):
- Implied Rate / Премия к КС / Carry Premium: green > 0, red < 0
- Intensity proportional to absolute value
- Funding: >0 green (SHORT profitable), <0 red (LONG profitable), =0 gray
- Action: SHORT green, LONG red, NEUTRAL gray
- Curve shape: КОНТАНГО green, БЭКВОРДАЦИЯ red
"""

from __future__ import annotations

import math
from typing import Any


# ---------------------------------------------------------------------------
# Validity check
# ---------------------------------------------------------------------------

def _valid(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return False
    return True


# ---------------------------------------------------------------------------
# Background-color helpers  (return CSS property strings)
# ---------------------------------------------------------------------------

_GREEN = "0, 180, 0"
_RED = "220, 40, 40"


def bg_rate(v: Any) -> str:
    """Green for positive rates, red for negative.

    Alpha scales with |value|: a 5% rate gets moderate color,
    20%+ gets near-maximum.
    """
    if not _valid(v) or v == 0:
        return ""
    alpha = 0.06 + min(abs(v) * 1.2, 0.30)
    rgb = _GREEN if v > 0 else _RED
    return f"background-color: rgba({rgb}, {alpha:.2f})"


def bg_deviation(v: Any) -> str:
    """For deviation/spread values — same logic, but scaled for smaller values."""
    if not _valid(v) or v == 0:
        return ""
    alpha = 0.06 + min(abs(v) * 8.0, 0.30)
    rgb = _GREEN if v > 0 else _RED
    return f"background-color: rgba({rgb}, {alpha:.2f})"


def bg_action(v: Any) -> str:
    """SHORT = green, LONG = red, NEUTRAL = gray."""
    if v == "SHORT":
        return f"background-color: rgba({_GREEN}, 0.20)"
    if v == "LONG":
        return f"background-color: rgba({_RED}, 0.20)"
    return "background-color: rgba(128, 128, 128, 0.10)"


def bg_shape(v: Any) -> str:
    """КОНТАНГО = green, БЭКВОРДАЦИЯ = red."""
    if v == "КОНТАНГО":
        return f"background-color: rgba({_GREEN}, 0.15)"
    if v == "БЭКВОРДАЦИЯ":
        return f"background-color: rgba({_RED}, 0.15)"
    return ""


def bg_sign(v: Any) -> str:
    """+fund = green, -fund = red, 0 = gray."""
    if v == "+fund":
        return f"background-color: rgba({_GREEN}, 0.20)"
    if v == "-fund":
        return f"background-color: rgba({_RED}, 0.20)"
    return "background-color: rgba(128, 128, 128, 0.10)"


# ---------------------------------------------------------------------------
# Format helpers  (return display strings; used in Styler.format())
# ---------------------------------------------------------------------------

def pct(decimals: int = 2, signed: bool = True):
    """Return a callable formatter for percentage values."""
    def _fmt(v: Any) -> str:
        if not _valid(v):
            return "\u2014"
        if signed:
            return f"{v * 100:+.{decimals}f}%"
        return f"{v * 100:.{decimals}f}%"
    return _fmt


def price(decimals: int = 2):
    """Return a callable formatter for prices with thousands separator."""
    def _fmt(v: Any) -> str:
        if not _valid(v):
            return "\u2014"
        return f"{v:,.{decimals}f}"
    return _fmt


def number(decimals: int = 6):
    """Return a callable formatter for small numbers (L1, L2, D, Funding)."""
    def _fmt(v: Any) -> str:
        if not _valid(v):
            return "\u2014"
        return f"{v:,.{decimals}f}"
    return _fmt


# ---------------------------------------------------------------------------
# Convenience: filter subset to existing columns
# ---------------------------------------------------------------------------

def _cols(df, names: list[str]) -> list[str]:
    """Return only those column names that exist in *df*."""
    return [c for c in names if c in df.columns]
