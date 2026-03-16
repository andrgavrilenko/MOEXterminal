"""Market Service — unified market picture for all other services.

Provides:
- MarketSnapshot (spots, futures, rates) via MOEX ISS live
- EquityRecord universe (from consensus.json + snapshot.json)
- SectorInfo map (from snapshot.json sector_signals)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from moex_dashboard.data.futures import load_all_futures
from moex_dashboard.data.rates import get_key_rate, load_rusfar
from moex_dashboard.data.spot import load_indices, load_spot_currencies, load_stock_spots
from moex_dashboard.models import MarketSnapshot

logger = logging.getLogger(__name__)

# Path to local JSON data (downloaded from Packman 2026-02-23)
_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"


# ---------------------------------------------------------------------------
# Domain models for equity universe and sectors
# ---------------------------------------------------------------------------

class EquityRecord(BaseModel):
    """Investable equity with basic fundamentals."""
    ticker: str
    name: str = ""
    sector: str = ""
    price: float | None = None
    change_pct: float | None = None
    turnover: float | None = None
    # Fundamentals from consensus.json
    target: float | None = None
    rec: float | None = None         # 1=buy, 2=hold, 3=sell (can be fractional avg)
    sales: float | None = None
    ebitda: float | None = None
    net_income: float | None = None
    net_debt: float | None = None
    roe: float | None = None
    dps: float | None = None        # dividend per share
    ev_cons: float | None = None
    shares: int | None = None


class SectorInfo(BaseModel):
    """Sector signal from Packman snapshot."""
    code: str               # e.g. "MOEXEU"
    name: str               # e.g. "Электроэн."
    date: str               # snapshot date
    price: float | None = None
    m1: float | None = None
    m3: float | None = None
    m6: float | None = None
    m12: float | None = None
    signal: str = ""        # "LONG" / "SHORT" / "FLAT"
    today_chg: float | None = None


# ---------------------------------------------------------------------------
# MarketService
# ---------------------------------------------------------------------------

class MarketService:
    """Single source of market truth.

    Usage:
        svc = MarketService()
        snapshot = svc.get_snapshot()
        equities = svc.get_equities()
        sectors = svc.get_sectors()
    """

    def __init__(self, data_dir: Path | None = None):
        self._data_dir = data_dir or _DATA_DIR
        # Lazy-loaded caches for static data
        self._consensus: list[dict] | None = None
        self._equities_snapshot: list[dict] | None = None
        self._sector_signals: list[dict] | None = None

    # -- Live market data ---------------------------------------------------

    def get_snapshot(self) -> MarketSnapshot:
        """Fetch live market snapshot from MOEX ISS.

        Handles partial failures: returns available data with stale=True.
        """
        stale = False

        try:
            spots = load_spot_currencies()
            spots.update(load_indices())
            spots.update(load_stock_spots())
        except Exception:
            logger.exception("Failed to load spot data")
            spots = {}
            stale = True

        try:
            futures = load_all_futures()
        except Exception:
            logger.exception("Failed to load futures data")
            futures = {}
            stale = True

        rusfar = load_rusfar()
        key_rate = get_key_rate()

        return MarketSnapshot(
            timestamp=datetime.now(),
            spots=spots,
            futures=futures,
            rusfar=rusfar,
            key_rate=key_rate,
            stale=stale,
        )

    # -- Equity universe ----------------------------------------------------

    def get_equities(self) -> list[EquityRecord]:
        """Return equity universe merged from live snapshot + consensus.

        Live data (snapshot.json equities): price, change, turnover, sector.
        Static data (consensus.json): target, rec, fundamentals.
        """
        equities_raw = self._load_equities_snapshot()
        consensus_map = self._build_consensus_map()

        result: list[EquityRecord] = []
        for eq in equities_raw:
            ticker = eq.get("secid", "")
            if not ticker:
                continue
            cons = consensus_map.get(ticker, {})
            result.append(EquityRecord(
                ticker=ticker,
                name=cons.get("name") or eq.get("name") or "",
                sector=cons.get("sector") or eq.get("sector") or "",
                price=eq.get("last"),
                change_pct=eq.get("change_pct"),
                turnover=eq.get("valtoday"),
                target=cons.get("target"),
                rec=cons.get("rec"),
                sales=cons.get("sales"),
                ebitda=cons.get("ebitda"),
                net_income=cons.get("net_income"),
                net_debt=cons.get("net_debt"),
                roe=cons.get("roe"),
                dps=cons.get("dps"),
                ev_cons=cons.get("ev_cons"),
                shares=cons.get("shares"),
            ))

        # Add consensus-only tickers not in equities snapshot
        seen = {r.ticker for r in result}
        for ticker, cons in consensus_map.items():
            if ticker not in seen:
                result.append(EquityRecord(
                    ticker=ticker,
                    name=cons.get("name", ""),
                    sector=cons.get("sector", ""),
                    target=cons.get("target"),
                    rec=cons.get("rec"),
                    sales=cons.get("sales"),
                    ebitda=cons.get("ebitda"),
                    net_income=cons.get("net_income"),
                    net_debt=cons.get("net_debt"),
                    roe=cons.get("roe"),
                    dps=cons.get("dps"),
                    ev_cons=cons.get("ev_cons"),
                    shares=cons.get("shares"),
                ))

        return result

    # -- Sector map ---------------------------------------------------------

    def get_sectors(self) -> list[SectorInfo]:
        """Return sector signals from snapshot.json."""
        raw = self._load_sector_signals()
        return [SectorInfo(**s) for s in raw]

    # -- Private loaders ----------------------------------------------------

    def _load_consensus(self) -> list[dict]:
        if self._consensus is None:
            path = self._data_dir / "consensus.json"
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    self._consensus = json.load(f)
            else:
                logger.warning("consensus.json not found at %s", path)
                self._consensus = []
        return self._consensus

    def _build_consensus_map(self) -> dict[str, dict]:
        """ticker -> consensus record."""
        return {r["ticker"]: r for r in self._load_consensus() if r.get("ticker")}

    def _load_equities_snapshot(self) -> list[dict]:
        if self._equities_snapshot is None:
            path = self._data_dir / "snapshot.json"
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                self._equities_snapshot = data.get("equities", [])
            else:
                logger.warning("snapshot.json not found at %s", path)
                self._equities_snapshot = []
        return self._equities_snapshot

    def _load_sector_signals(self) -> list[dict]:
        if self._sector_signals is None:
            path = self._data_dir / "snapshot.json"
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                self._sector_signals = data.get("sector_signals", [])
            else:
                logger.warning("snapshot.json not found at %s", path)
                self._sector_signals = []
        return self._sector_signals
