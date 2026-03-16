"""Sector Momentum Service.

Ranks 8 MOEX sector indices by momentum and assigns LONG/SHORT/FLAT signals.

Two modes:
- snapshot mode: uses pre-computed signals from snapshot.json (fast, no API)
- live mode:     fetches prices from MOEX ISS, calculates momentum itself

Signal logic (matches Packman Monitor):
  - Rank by m3 (3-month momentum) descending
  - Top-2 → LONG
  - Bottom-2 → SHORT
  - Остальные → FLAT
  - Rebalance: monthly
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd
from pydantic import BaseModel

from moex_dashboard.data.moex_api import fetch_iss
from moex_dashboard.services.market_service import MarketService, SectorInfo

logger = logging.getLogger(__name__)

# 8 standard MOEX sector indices
SECTOR_CODES = ["MOEXEU", "MOEXOG", "MOEXMM", "MOEXFN",
                "MOEXCN", "MOEXTL", "MOEXTN", "MOEXCH"]

SECTOR_NAMES = {
    "MOEXEU": "Электроэн.",
    "MOEXOG": "Нефть и газ",
    "MOEXMM": "Металлы",
    "MOEXFN": "Финансы",
    "MOEXCN": "Потребит.",
    "MOEXTL": "Телеком",
    "MOEXTN": "Транспорт",
    "MOEXCH": "Химия",
}

# Momentum windows in calendar days
_WINDOWS = {"m1": 30, "m3": 91, "m6": 182, "m12": 365}

# Rank thresholds
_LONG_TOP_N = 2
_SHORT_BOTTOM_N = 2


class SectorSignal(BaseModel):
    """Sector signal with momentum metrics and rank."""
    code: str
    name: str
    date: str                   # data date (ISO)
    price: float | None = None
    m1: float | None = None
    m3: float | None = None
    m6: float | None = None
    m12: float | None = None
    signal: str = "FLAT"        # "LONG" / "SHORT" / "FLAT"
    rank: int | None = None     # 1 = best m3, 8 = worst
    today_chg: float | None = None


class SectorMomentumService:
    """Sector momentum ranking service.

    Usage:
        svc = SectorMomentumService(market_service)
        signals = svc.get_signals()                # from snapshot.json
        signals = svc.get_signals(live=True)       # from MOEX ISS API
        leaderboard = svc.get_leaderboard()        # sorted by m3
    """

    def __init__(self, market_service: MarketService | None = None):
        self._market_svc = market_service or MarketService()

    # -- Public API ---------------------------------------------------------

    def get_signals(self, live: bool = False) -> list[SectorSignal]:
        """Return sector signals with rank and momentum.

        Args:
            live: If True, fetch current prices + 12M history from MOEX ISS
                  and recalculate momentum. Slower (~9 API requests).
                  If False, use pre-computed data from snapshot.json (fast).
        """
        if live:
            return self._compute_live_signals()
        return self._from_snapshot()

    def get_leaderboard(self, live: bool = False) -> pd.DataFrame:
        """Return sector signals as a DataFrame sorted by m3 (best first)."""
        signals = self.get_signals(live=live)
        rows = [s.model_dump() for s in signals]
        df = pd.DataFrame(rows)
        if not df.empty and "m3" in df.columns:
            df.sort_values("m3", ascending=False, inplace=True)
            df.reset_index(drop=True, inplace=True)
        return df

    # -- Snapshot mode (fast) -----------------------------------------------

    def _from_snapshot(self) -> list[SectorSignal]:
        """Load signals from snapshot.json via market_service."""
        raw: list[SectorInfo] = self._market_svc.get_sectors()
        if not raw:
            return []

        # Assign ranks based on m3
        ranked = _rank_by_m3(raw)
        n = len(ranked)

        result: list[SectorSignal] = []
        for rank, sector in enumerate(ranked, start=1):
            if rank <= _LONG_TOP_N:
                signal = "LONG"
            elif rank > n - _SHORT_BOTTOM_N:
                signal = "SHORT"
            else:
                signal = "FLAT"

            result.append(SectorSignal(
                code=sector.code,
                name=sector.name,
                date=sector.date,
                price=sector.price,
                m1=sector.m1,
                m3=sector.m3,
                m6=sector.m6,
                m12=sector.m12,
                signal=signal,
                rank=rank,
                today_chg=sector.today_chg,
            ))

        return result

    # -- Live mode (MOEX ISS) -----------------------------------------------

    def _compute_live_signals(self) -> list[SectorSignal]:
        """Fetch current prices + 12M history, compute momentum live."""
        today = date.today()

        # 1. Current prices for all sectors (one batch request)
        current_prices = _fetch_current_prices()

        # 2. Historical prices per sector (8 requests)
        history: dict[str, pd.Series] = {}
        for code in SECTOR_CODES:
            hist = _fetch_history(code, today - timedelta(days=380), today)
            if hist is not None and not hist.empty:
                history[code] = hist

        # 3. Calculate momentum for each sector
        result: list[SectorSignal] = []
        for code in SECTOR_CODES:
            price = current_prices.get(code)
            hist = history.get(code)
            today_chg = None

            m1 = m3 = m6 = m12 = None
            if hist is not None and not hist.empty and price is not None:
                m1 = _momentum(price, hist, today, _WINDOWS["m1"])
                m3 = _momentum(price, hist, today, _WINDOWS["m3"])
                m6 = _momentum(price, hist, today, _WINDOWS["m6"])
                m12 = _momentum(price, hist, today, _WINDOWS["m12"])

                # Today's change from yesterday
                if len(hist) >= 2:
                    prev = float(hist.iloc[-1])
                    if prev > 0:
                        today_chg = (price / prev - 1) * 100

            result.append(SectorSignal(
                code=code,
                name=SECTOR_NAMES.get(code, code),
                date=today.isoformat(),
                price=price,
                m1=m1,
                m3=m3,
                m6=m6,
                m12=m12,
                signal="FLAT",  # will be assigned below
                today_chg=today_chg,
            ))

        # 4. Rank and assign signals
        return _assign_signals(result)


# ---------------------------------------------------------------------------
# MOEX ISS helpers
# ---------------------------------------------------------------------------

def _fetch_current_prices() -> dict[str, float]:
    """Fetch current CURRENTVALUE for all 8 sector indices (one request)."""
    try:
        blocks = fetch_iss(
            "/engines/stock/markets/index/securities.json",
            params={
                "securities": ",".join(SECTOR_CODES),
                "iss.only": "marketdata",
                "marketdata.columns": "SECID,CURRENTVALUE",
            },
        )
        if "marketdata" not in blocks:
            return {}
        df = blocks["marketdata"]
        result: dict[str, float] = {}
        for _, row in df.iterrows():
            val = row.get("CURRENTVALUE")
            if val is not None and float(val) > 0:
                result[str(row["SECID"])] = float(val)
        return result
    except Exception:
        logger.exception("Failed to fetch sector prices")
        return {}


def _fetch_history(code: str, from_date: date, till_date: date) -> pd.Series | None:
    """Fetch daily CLOSE prices for one sector index over a date range.

    Returns:
        pd.Series indexed by date, sorted ascending. None on failure.
    """
    try:
        blocks = fetch_iss(
            f"/history/engines/stock/markets/index/securities/{code}.json",
            params={
                "from": from_date.isoformat(),
                "till": till_date.isoformat(),
                "iss.only": "history",
                "history.columns": "TRADEDATE,CLOSE",
            },
        )
        if "history" not in blocks:
            return None
        df = blocks["history"]
        if df.empty:
            return None

        df["TRADEDATE"] = pd.to_datetime(df["TRADEDATE"], errors="coerce")
        df["CLOSE"] = pd.to_numeric(df["CLOSE"], errors="coerce")
        df.dropna(inplace=True)
        df.sort_values("TRADEDATE", inplace=True)
        return df.set_index("TRADEDATE")["CLOSE"]
    except Exception:
        logger.exception("Failed to fetch history for %s", code)
        return None


def _momentum(
    current_price: float,
    hist: pd.Series,
    today: date,
    days_back: int,
) -> float | None:
    """Return (current / past_price - 1) * 100 for a given lookback window.

    Finds the closest available trading day to (today - days_back).
    Uses ffill to handle weekends/holidays.
    """
    if not isinstance(hist.index, pd.DatetimeIndex) or hist.empty:
        return None

    target_date = pd.Timestamp(today - timedelta(days=days_back))

    # Get the closest available date at or before the target
    available = hist.index[hist.index <= target_date]
    if available.empty:
        return None

    past_price = float(hist.loc[available[-1]])
    if past_price <= 0:
        return None

    return (current_price / past_price - 1) * 100


# ---------------------------------------------------------------------------
# Signal assignment helpers
# ---------------------------------------------------------------------------

def _rank_by_m3(sectors: list) -> list:
    """Sort sectors by m3 descending. None m3 goes to bottom."""
    return sorted(
        sectors,
        key=lambda s: (s.m3 is not None, s.m3 if s.m3 is not None else -999),
        reverse=True,
    )


def _assign_signals(signals: list[SectorSignal]) -> list[SectorSignal]:
    """Rank signals by m3, assign LONG/SHORT/FLAT."""
    ranked = sorted(
        signals,
        key=lambda s: (s.m3 is not None, s.m3 if s.m3 is not None else -999),
        reverse=True,
    )
    n = len(ranked)
    for rank, s in enumerate(ranked, start=1):
        s.rank = rank
        if rank <= _LONG_TOP_N:
            s.signal = "LONG"
        elif rank > n - _SHORT_BOTTOM_N:
            s.signal = "SHORT"
        else:
            s.signal = "FLAT"
    return ranked
