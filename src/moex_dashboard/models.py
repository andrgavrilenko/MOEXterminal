"""Data models for market data and signals."""

from datetime import date, datetime

from pydantic import BaseModel


class SpotQuote(BaseModel):
    secid: str
    name: str
    price: float


class FuturesContract(BaseModel):
    secid: str
    asset_code: str
    expiry_date: date
    price: float | None
    days_to_expiry: int


class MarketSnapshot(BaseModel):
    timestamp: datetime
    spots: dict[str, SpotQuote]  # secid -> SpotQuote
    futures: dict[str, list[FuturesContract]]  # asset_code -> sorted by expiry
    rusfar: float | None
    key_rate: float
    stale: bool = False
