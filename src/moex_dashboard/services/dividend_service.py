"""Dividend Service — upcoming dividend calendar with tier classification.

Data sources:
  data/dividends.json      — 304 records, upcoming + historical, with DSI scores
  data/declared_divs.json  — confirmed (declared) dividends with payment dates

Tier classification:
  Tier 1: DSI >= 0.5  (reliable dividend history, high probability of payment)
  Tier 2: DSI >= 0.25 (moderate history)
  Other:  DSI <  0.25 or no DSI

Dividend capture window:
  Ex-date ≈ rec_date − 2 trading days (T+2 settlement on MOEX)
  Entry:  before ex-date
  Exit:   D+1 to D+6 post-ex (gap fill, per Packman Monitor strategy)
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"

# Tier thresholds (DSI — Dividend Stability Index, 0–1)
_TIER1_DSI = 0.5
_TIER2_DSI = 0.25


# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------

class DividendRecord(BaseModel):
    """Single upcoming dividend event."""
    ticker: str
    name: str = ""
    sector: str = ""
    period: str = ""
    div: float                          # dividend amount (RUB)
    div_yield: float                    # % yield at capture price
    price: float | None = None          # stock price at snapshot time
    rec_date: date                      # record (cut-off) date
    ex_date: date                       # estimated ex-date = rec_date - 2 days
    days_to_rec: int                    # calendar days from today
    days_to_ex: int                     # calendar days from today to ex-date
    dsi: float = 0.0                    # dividend stability index (0–1)
    tier: int = 0                       # 1, 2, or 0 (unclassified)
    confirmed: bool = False             # True if in declared_divs.json
    payment_date: date | None = None    # from declared_divs.json


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class DividendService:
    """Upcoming dividend calendar for MOEX equities.

    Usage:
        svc = DividendService()
        records = svc.get_calendar(days=90)        # list[DividendRecord]
        df      = svc.get_table(days=90)           # pd.DataFrame
        tier1   = svc.get_tier1(days=60)           # only Tier 1
    """

    def __init__(self, data_dir: Path | None = None):
        self._data_dir = data_dir or _DATA_DIR
        self._divs_raw: list[dict] | None = None
        self._declared_raw: dict | None = None

    # -- Public API ---------------------------------------------------------

    def get_calendar(
        self,
        days: int = 180,
        min_tier: int = 0,
        today: date | None = None,
    ) -> list[DividendRecord]:
        """Return upcoming dividend events within the next *days* calendar days.

        Args:
            days:     Look-ahead window in calendar days.
            min_tier: Minimum tier to include (0 = all, 1 = Tier 1 only, etc.)
            today:    Override today's date (for testing).
        """
        ref = today or date.today()
        cutoff = ref + timedelta(days=days)

        declared = self._load_declared()
        records: list[DividendRecord] = []

        for raw in self._load_divs():
            rec = _parse_record(raw, ref, declared)
            if rec is None:
                continue
            if rec.rec_date < ref or rec.rec_date > cutoff:
                continue
            # min_tier=1 → only tier 1; min_tier=2 → tier 1 and 2; 0 → all
            if min_tier > 0 and not (1 <= rec.tier <= min_tier):
                continue
            records.append(rec)

        records.sort(key=lambda r: r.rec_date)
        return records

    def get_table(self, days: int = 180, min_tier: int = 0,
                  today: date | None = None) -> pd.DataFrame:
        """Return calendar as display-ready DataFrame."""
        records = self.get_calendar(days=days, min_tier=min_tier, today=today)
        if not records:
            return pd.DataFrame()

        rows = []
        for r in records:
            rows.append({
                "Тир": f"T{r.tier}" if r.tier else "—",
                "Тикер": r.ticker,
                "Название": r.name,
                "Сектор": r.sector,
                "Период": r.period,
                "Дивиденд": r.div,
                "Дох.%": r.div_yield / 100,
                "Рек.дата": r.rec_date.strftime("%d.%m.%Y"),
                "Экс-дата": r.ex_date.strftime("%d.%m.%Y"),
                "Дней до экс": r.days_to_ex,
                "DSI": r.dsi,
                "Подтв.": "✓" if r.confirmed else "",
            })

        return pd.DataFrame(rows)

    def get_tier1(self, days: int = 60, today: date | None = None) -> list[DividendRecord]:
        """Convenience: only Tier 1 events in the next *days* days."""
        return self.get_calendar(days=days, min_tier=1, today=today)

    # -- Private loaders ----------------------------------------------------

    def _load_divs(self) -> list[dict]:
        if self._divs_raw is None:
            path = self._data_dir / "dividends.json"
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    self._divs_raw = json.load(f)
            else:
                logger.warning("dividends.json not found at %s", path)
                self._divs_raw = []
        return self._divs_raw

    def _load_declared(self) -> dict[str, list[dict]]:
        if self._declared_raw is None:
            path = self._data_dir / "declared_divs.json"
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    self._declared_raw = json.load(f)
            else:
                self._declared_raw = {}
        return self._declared_raw


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_record(
    raw: dict,
    ref: date,
    declared: dict[str, list[dict]],
) -> DividendRecord | None:
    """Parse a raw dict from dividends.json into DividendRecord. Returns None on failure."""
    ticker = raw.get("ticker", "")
    if not ticker:
        return None

    rec_date_str = raw.get("rec_date", "")
    if not rec_date_str:
        return None

    try:
        rec_date = datetime.strptime(rec_date_str, "%d.%m.%Y").date()
    except ValueError:
        return None

    div = raw.get("div")
    if div is None:
        return None
    div = float(div)

    div_yield = float(raw.get("yield") or 0.0)
    dsi = float(raw.get("dsi") or 0.0)
    tier = _classify_tier(dsi)

    ex_date = rec_date - timedelta(days=2)
    days_to_rec = (rec_date - ref).days
    days_to_ex = (ex_date - ref).days

    # Check declared_divs for confirmation + payment date
    confirmed = False
    payment_date = None
    declared_list = declared.get(ticker, [])
    for d in declared_list:
        try:
            d_rec = date.fromisoformat(d.get("record_date", ""))
            if d_rec == rec_date:
                confirmed = True
                pd_str = d.get("payment_date", "")
                if pd_str:
                    payment_date = date.fromisoformat(pd_str)
                break
        except (ValueError, TypeError):
            continue

    return DividendRecord(
        ticker=ticker,
        name=raw.get("name", ""),
        sector=raw.get("sector", ""),
        period=raw.get("period", ""),
        div=div,
        div_yield=div_yield,
        price=raw.get("price") or None,
        rec_date=rec_date,
        ex_date=ex_date,
        days_to_rec=days_to_rec,
        days_to_ex=days_to_ex,
        dsi=dsi,
        tier=tier,
        confirmed=confirmed,
        payment_date=payment_date,
    )


def _classify_tier(dsi: float) -> int:
    if dsi >= _TIER1_DSI:
        return 1
    if dsi >= _TIER2_DSI:
        return 2
    return 0
