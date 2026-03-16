"""Momentum Portfolio Service — top stock picker within LONG sectors.

Pipeline:
  SectorMomentumService.get_signals()          → LONG sector codes
  MarketService.get_equities()                 → equity universe
  _score()                                     → composite score per stock
  get_picks() / get_table()                    → ranked watchlist

Scoring formula (higher = better):
  upside_score   = (target / price - 1) * 100    [% analyst upside]
  rec_score      = (3 - rec) * 15                [buy=30, hold=15, sell=0]
  div_score      = min(div_yield_pct, 20)        [% yield, capped at 20]
  score          = upside_score + rec_score + div_score

Only stocks with at least one data point (target OR rec OR dps) are scored.
"""

from __future__ import annotations

import logging

import pandas as pd
from pydantic import BaseModel

from moex_dashboard.services.market_service import EquityRecord, MarketService
from moex_dashboard.services.sector_momentum_service import (
    SECTOR_NAMES,
    SectorMomentumService,
    SectorSignal,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Static sector → ticker composition (MOEX index constituents, Feb 2026)
# Source: CLAUDE.md / Packman Monitor
# ---------------------------------------------------------------------------

SECTOR_TICKERS: dict[str, list[str]] = {
    "MOEXEU": ["IRAO", "LSNGP", "MSNG", "UPRO", "FEES", "MRKP", "HYDR",
               "MSRS", "MRKC", "MRKV", "MRKU", "OGKB", "TGKA", "ELFV"],
    "MOEXOG": ["GAZP", "LKOH", "NVTK", "TATN", "ROSN", "SNGS", "SNGSP",
               "TATNP", "TRNFP", "BANEP", "RNFT"],
    "MOEXMM": ["GMKN", "PLZL", "CHMF", "RUAL", "NLMK", "MAGN", "ALRS",
               "VSMO", "ENPG", "UGLD", "SELG", "MTLR", "TRMK", "RASP", "MTLRP"],
    "MOEXFN": ["VTBR", "T", "MOEX", "SBER", "SVCB", "DOMRF", "CBOM",
               "BSPB", "RENI", "SBERP", "LEAS", "SFIN", "MBNK", "SPBE"],
    "MOEXCN": ["MGNT", "MDMG", "X5", "RAGR", "LENT", "GEMC", "AQUA",
               "FIXR", "OZPH", "EUTR", "BELU", "PRMD", "VSEH", "APTK",
               "WUSH", "HNFG", "SVAV"],
    "MOEXTL": ["MTSS", "RTKM", "MGTSP", "RTKMP"],
    "MOEXTN": ["AFLT", "FLOT", "NMTP", "FESH", "NKHP"],
    "MOEXCH": ["PHOR", "AKRN", "NKNC", "NKNCP"],
}

# Reverse map: ticker → sector code (first match wins for cross-listed names)
_TICKER_TO_SECTOR: dict[str, str] = {
    ticker: code
    for code, tickers in SECTOR_TICKERS.items()
    for ticker in tickers
}


# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------

class StockPick(BaseModel):
    """Scored stock candidate within a LONG sector."""
    ticker: str
    name: str = ""
    sector_code: str                    # e.g. "MOEXFN"
    sector_name: str                    # e.g. "Финансы"
    price: float | None = None
    change_pct: float | None = None     # today's % change
    target: float | None = None         # analyst target price
    upside: float | None = None         # (target/price - 1) * 100
    rec: float | None = None            # 1=buy, 2=hold, 3=sell
    dps: float | None = None            # dividend per share (annual)
    div_yield: float | None = None      # dps/price * 100
    score: float = 0.0                  # composite score


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class MomentumPortfolioService:
    """Pick top stocks within LONG sectors.

    Usage:
        svc = MomentumPortfolioService()
        signals = sector_svc.get_signals()
        picks = svc.get_picks(signals, top_n=5)
        df    = svc.get_table(signals, top_n=5)
    """

    def __init__(self, market_service: MarketService | None = None):
        self._market_svc = market_service or MarketService()

    def get_picks(
        self,
        signals: list[SectorSignal],
        top_n: int = 5,
        include_flat: bool = False,
    ) -> list[StockPick]:
        """Return top_n scored stocks per LONG sector.

        Args:
            signals:      Output of SectorMomentumService.get_signals().
            top_n:        Max stocks per sector to return.
            include_flat: If True, also include FLAT sectors.
        """
        target_signals = {"LONG", "FLAT"} if include_flat else {"LONG"}
        active_codes = {s.code for s in signals if s.signal in target_signals}

        if not active_codes:
            return []

        equities = self._market_svc.get_equities()
        equity_map: dict[str, EquityRecord] = {e.ticker: e for e in equities}

        picks: list[StockPick] = []
        for code in active_codes:
            tickers = SECTOR_TICKERS.get(code, [])
            sector_picks = []
            for ticker in tickers:
                eq = equity_map.get(ticker)
                if eq is None:
                    continue
                pick = _build_pick(ticker, eq, code)
                if pick is not None:
                    sector_picks.append(pick)

            # Sort by score descending, take top_n
            sector_picks.sort(key=lambda p: p.score, reverse=True)
            picks.extend(sector_picks[:top_n])

        return picks

    def get_table(
        self,
        signals: list[SectorSignal],
        top_n: int = 5,
        include_flat: bool = False,
    ) -> pd.DataFrame:
        """Return picks as display-ready DataFrame."""
        picks = self.get_picks(signals, top_n=top_n, include_flat=include_flat)
        if not picks:
            return pd.DataFrame()

        rows = []
        for p in picks:
            rows.append({
                "Сектор": p.sector_name,
                "Тикер": p.ticker,
                "Название": p.name,
                "Цена": p.price,
                "Δ%": p.change_pct / 100 if p.change_pct is not None else None,
                "Таргет": p.target,
                "Апсайд%": p.upside / 100 if p.upside is not None else None,
                "Рек.": _rec_label(p.rec),
                "Дивиденд%": p.div_yield / 100 if p.div_yield is not None else None,
                "Скор": round(p.score, 1),
            })

        return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_pick(ticker: str, eq: EquityRecord, sector_code: str) -> StockPick | None:
    """Build a scored StockPick from an EquityRecord. Returns None if unscorable."""
    price = eq.price
    target = eq.target
    rec = eq.rec
    dps = eq.dps

    # Need at least one signal to be useful
    if target is None and rec is None and dps is None:
        return None

    upside = None
    upside_score = 0.0
    if target is not None and price is not None and price > 0:
        upside = (target / price - 1) * 100
        upside_score = upside  # can be negative (downside)

    rec_score = 0.0
    if rec is not None:
        rec_score = (3.0 - rec) * 15.0  # buy=30, hold=15, sell=0

    div_yield = None
    div_score = 0.0
    if dps is not None and price is not None and price > 0 and dps > 0:
        div_yield = dps / price * 100
        div_score = min(div_yield, 20.0)

    score = upside_score + rec_score + div_score

    return StockPick(
        ticker=ticker,
        name=eq.name,
        sector_code=sector_code,
        sector_name=SECTOR_NAMES.get(sector_code, sector_code),
        price=price,
        change_pct=eq.change_pct,
        target=target,
        upside=upside,
        rec=rec,
        dps=dps,
        div_yield=div_yield,
        score=score,
    )


_REC_LABELS = {1: "BUY", 2: "HOLD", 3: "SELL"}


def _rec_label(rec: float | None) -> str:
    if rec is None:
        return "—"
    if rec <= 1.5:
        return "BUY"
    if rec <= 2.5:
        return "HOLD"
    return "SELL"
