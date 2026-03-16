"""Funding analysis for perpetual (eternal) FX futures on MOEX.

Perpetual futures use a daily funding mechanism to keep their price
aligned with the spot.  The funding formula is:

    Funding = MIN(L2, MAX(-L2, MIN(-L1, D) + MAX(L1, D)))

where:
    D  = avg(PerpPrice_i - SpotPrice_i) over minute candles during
         the trading session (10:00 -> evening clearing)
    L1 = K1 * SpotPrice   (dead zone — funding is zero if |D| < L1)
    L2 = K2 * SpotPrice   (cap — maximum absolute funding)

See ``moex_funding.md`` for the full specification.
"""

from __future__ import annotations

import pandas as pd

from moex_dashboard.calc.arbitrage import implied_rate
from moex_dashboard.config import ASSET_MAP
from moex_dashboard.data.perpetual import PERPETUAL_MAP
from moex_dashboard.models import MarketSnapshot


# ---------------------------------------------------------------------------
# Trading session boundaries (Moscow time, hour:minute)
# ---------------------------------------------------------------------------

_SESSION_START_HOUR = 10
_SESSION_START_MIN = 0

# Intermediate clearing gap: 14:00–14:05 — excluded from D calculation.
_CLEARING_GAP_START_HOUR = 14
_CLEARING_GAP_START_MIN = 0
_CLEARING_GAP_END_HOUR = 14
_CLEARING_GAP_END_MIN = 5

# Candle timestamp tolerance when matching perp vs spot candles.
_MATCH_TOLERANCE = pd.Timedelta(minutes=2)


# ---------------------------------------------------------------------------
# Core funding formulas
# ---------------------------------------------------------------------------


def calc_d(
    perp_candles: pd.DataFrame,
    spot_candles: pd.DataFrame,
    price_divisor: float = 1.0,
) -> tuple[float | None, str]:
    """Calculate D = avg(PerpClose - SpotClose) from minute candles.

    Candles are matched by timestamp with a tolerance of 2 minutes.
    Only candles within the main trading session (10:00 onward, excluding
    the 14:00-14:05 intermediate clearing window) are used.

    Args:
        perp_candles: DataFrame with ``begin`` (datetime) and ``close``
            columns for the perpetual future.
        spot_candles: DataFrame with ``begin`` (datetime) and ``close``
            columns for the spot instrument.
        price_divisor: Divisor to normalize the perpetual candle close
            price to per-unit (same scale as spot).

    Returns:
        Tuple of (D value or None, quality string).
        Quality is one of:
        - ``"full"``         — >= 200 matched candles
        - ``"partial"``      — 30..199 matched candles
        - ``"insufficient"`` — < 30 matched candles (D is ``None``)
    """
    if perp_candles.empty or spot_candles.empty:
        return None, "insufficient"

    # Work on copies to avoid mutating the caller's DataFrames.
    perp = perp_candles[["begin", "close"]].copy()
    spot = spot_candles[["begin", "close"]].copy()

    # Ensure datetime dtype.
    perp["begin"] = pd.to_datetime(perp["begin"], errors="coerce")
    spot["begin"] = pd.to_datetime(spot["begin"], errors="coerce")
    perp.dropna(subset=["begin"], inplace=True)
    spot.dropna(subset=["begin"], inplace=True)

    if perp.empty or spot.empty:
        return None, "insufficient"

    # Normalize perpetual close price.
    perp["close"] = perp["close"] / price_divisor

    # Filter to trading session (>=10:00) and exclude intermediate clearing
    # gap (14:00-14:05).
    perp = _filter_session(perp)
    spot = _filter_session(spot)

    if perp.empty or spot.empty:
        return None, "insufficient"

    # Match by nearest timestamp within tolerance using merge_asof.
    perp = perp.sort_values("begin").reset_index(drop=True)
    spot = spot.sort_values("begin").reset_index(drop=True)

    merged = pd.merge_asof(
        perp.rename(columns={"close": "perp_close"}),
        spot.rename(columns={"close": "spot_close"}),
        on="begin",
        tolerance=_MATCH_TOLERANCE,
        direction="nearest",
    )

    merged.dropna(subset=["perp_close", "spot_close"], inplace=True)

    n = len(merged)
    if n < 30:
        return None, "insufficient"

    d_value = float((merged["perp_close"] - merged["spot_close"]).mean())

    quality = "full" if n >= 200 else "partial"
    return d_value, quality


def calc_funding(d: float, l1: float, l2: float) -> float:
    """Apply the MOEX funding formula.

    Formula:
        Funding = MIN(L2, MAX(-L2, MIN(-L1, D) + MAX(L1, D)))

    Args:
        d: Average deviation (PerpPrice - SpotPrice) over the session.
        l1: Dead-zone boundary (K1 * SpotPrice).
        l2: Cap boundary (K2 * SpotPrice).

    Returns:
        Funding value in the same units as *d* (e.g. RUB per unit).
    """
    return min(l2, max(-l2, min(-l1, d) + max(l1, d)))


def predicted_funding_sign(d: float, l1: float) -> int:
    """Predict the sign of the funding from the current D value.

    Returns:
        +1 if D > L1  (positive funding, longs pay shorts),
        -1 if D < -L1 (negative funding, shorts pay longs),
         0 if |D| <= L1 (within dead zone, no funding).
    """
    if abs(d) <= l1:
        return 0
    return 1 if d > 0 else -1


def suggested_action(pred_sign: int) -> str:
    """Translate a predicted funding sign into a trading suggestion.

    - Positive funding -> longs pay, so SHORT the perpetual.
    - Negative funding -> shorts pay, so LONG the perpetual.
    - Zero -> no clear edge.

    Returns:
        One of ``"SHORT"``, ``"LONG"``, or ``"NEUTRAL"``.
    """
    if pred_sign > 0:
        return "SHORT"
    if pred_sign < 0:
        return "LONG"
    return "NEUTRAL"


def funding_annualized(funding: float, spot: float) -> float | None:
    """Annualize a single-day funding payment as a fraction of spot.

    Formula: (funding / spot) * 365

    Args:
        funding: Daily funding value (RUB per unit).
        spot: Current spot price.

    Returns:
        Annualized funding rate (e.g. 0.05 for 5%), or None if spot <= 0.
    """
    if spot <= 0:
        return None
    return (funding / spot) * 365


# ---------------------------------------------------------------------------
# Pipeline: build the full funding analysis table
# ---------------------------------------------------------------------------

# Map perpetual SECID -> ASSET_MAP asset code for the nearest dated future
# of the same underlying.  Used to pull the implied rate from the regular
# (non-perpetual) futures curve.
_PERP_TO_ASSET_CODE: dict[str, str] = {
    "USDRUBF": "Si",
    "EURRUBF": "Eu",
    "CNYRUBF": "CR",
}


def build_funding_table(
    snapshot: MarketSnapshot,
    perp_prices: dict[str, float],
    perp_specs: dict[str, dict],
    candles_data: dict[str, dict[str, pd.DataFrame]],
) -> pd.DataFrame:
    """Build the full funding analysis DataFrame.

    Args:
        snapshot: Current market snapshot (spots, futures, rates).
        perp_prices: SECID -> normalized perpetual price (from
            ``load_perpetual_prices``).
        perp_specs: SECID -> {"k1", "k2", "lotsize"} (from
            ``load_perpetual_specs``).
        candles_data: SECID -> {"perp": DataFrame, "spot": DataFrame}
            with minute candles for each perpetual/spot pair (from
            ``load_minute_candles``).

    Returns:
        DataFrame with columns:
            Валюта, Spot, Perp, D, L1, L2, Funding, Funding Ann.,
            Predicted, Action, Implied Rate, Cash Rate,
            Funding vs Cash, Implied vs Cash
    """
    rows: list[dict] = []

    for perp_secid, meta in PERPETUAL_MAP.items():
        spot_secid = meta["spot_secid"]
        name = meta["name"]
        divisor = meta["price_divisor"]

        # Spot price from the snapshot.
        spot_quote = snapshot.spots.get(spot_secid)
        if spot_quote is None or spot_quote.price is None or spot_quote.price <= 0:
            continue
        spot_price = spot_quote.price

        # Perpetual price.
        perp_price = perp_prices.get(perp_secid)
        if perp_price is None:
            continue

        # K1 / K2 from specs.
        spec = perp_specs.get(perp_secid, {})
        k1 = spec.get("k1", 0.0001)
        k2 = spec.get("k2", 0.001)

        l1 = k1 * spot_price
        l2 = k2 * spot_price

        # D from candles.
        candle_pair = candles_data.get(perp_secid, {})
        perp_candles = candle_pair.get("perp", pd.DataFrame())
        spot_candles = candle_pair.get("spot", pd.DataFrame())

        d_value, quality = calc_d(perp_candles, spot_candles, price_divisor=divisor)

        # Funding calculations (only if D is available).
        funding_val = None
        funding_ann = None
        pred_sign = 0
        action = "NEUTRAL"

        if d_value is not None:
            funding_val = calc_funding(d_value, l1, l2)
            funding_ann = funding_annualized(funding_val, spot_price)
            pred_sign = predicted_funding_sign(d_value, l1)
            action = suggested_action(pred_sign)

        # Implied rate from the nearest dated future of the same underlying.
        impl_rate = nearest_implied_rate(snapshot, perp_secid)

        # Cash rate: use RUSFAR if available, otherwise key rate.
        cash_rate = snapshot.rusfar if snapshot.rusfar is not None else snapshot.key_rate

        # Derived comparisons.
        funding_vs_cash = None
        implied_vs_cash = None
        if funding_ann is not None:
            funding_vs_cash = funding_ann - cash_rate
        if impl_rate is not None:
            implied_vs_cash = impl_rate - cash_rate

        rows.append(
            {
                "Валюта": name,
                "Spot": spot_price,
                "Perp": perp_price,
                "D": d_value,
                "Quality": quality,
                "L1": l1,
                "L2": l2,
                "Funding": funding_val,
                "Funding Ann.": funding_ann,
                "Predicted": _sign_label(pred_sign),
                "Action": action,
                "Implied Rate": impl_rate,
                "Cash Rate": cash_rate,
                "Funding vs Cash": funding_vs_cash,
                "Implied vs Cash": implied_vs_cash,
            }
        )

    df = pd.DataFrame(rows)
    if not df.empty:
        df.sort_values("Валюта", inplace=True)
        df.reset_index(drop=True, inplace=True)
    return df


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _filter_session(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only candles from the main trading session (>= 10:00),
    excluding the 14:00-14:05 intermediate clearing gap."""
    mask_after_open = (
        (df["begin"].dt.hour > _SESSION_START_HOUR)
        | (
            (df["begin"].dt.hour == _SESSION_START_HOUR)
            & (df["begin"].dt.minute >= _SESSION_START_MIN)
        )
    )

    # Exclude 14:00-14:04 (candles with begin in [14:00, 14:05)).
    mask_clearing_gap = (
        (df["begin"].dt.hour == _CLEARING_GAP_START_HOUR)
        & (df["begin"].dt.minute >= _CLEARING_GAP_START_MIN)
        & (df["begin"].dt.minute < _CLEARING_GAP_END_MIN)
    )

    return df[mask_after_open & ~mask_clearing_gap].copy()


def nearest_implied_rate(
    snapshot: MarketSnapshot, perp_secid: str
) -> float | None:
    """Return the implied rate of the nearest dated future for the same
    underlying as the given perpetual."""
    asset_code = _PERP_TO_ASSET_CODE.get(perp_secid)
    if asset_code is None:
        return None

    contracts = snapshot.futures.get(asset_code, [])
    if not contracts:
        return None

    mapping = ASSET_MAP.get(asset_code)
    if mapping is None:
        return None

    spot_secid = mapping["spot_secid"]
    spot_quote = snapshot.spots.get(spot_secid)
    if spot_quote is None or spot_quote.price is None or spot_quote.price <= 0:
        return None
    spot_price = spot_quote.price

    # Pick the nearest (front) contract with a valid price.
    valid = [
        c for c in contracts if c.price is not None and c.days_to_expiry > 0
    ]
    if not valid:
        return None
    valid.sort(key=lambda c: c.days_to_expiry)
    front = valid[0]

    return implied_rate(front.price, spot_price, front.days_to_expiry)


def _sign_label(sign: int) -> str:
    """Human-readable label for the predicted funding sign."""
    if sign > 0:
        return "+fund"
    if sign < 0:
        return "-fund"
    return "0"
