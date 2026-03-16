"""Funding Service — perpetual FX futures funding analysis.

Owns the full data pipeline for perpetual futures:
  data/perpetual.py  →  FundingService  →  FundingResult / DataFrame

Separated from arbitrage_service because:
- Different data (minute candles, heavy to fetch)
- Different TTL (60s vs 30s for snapshot)
- Used both standalone and as an input to arbitrage_service
"""

from __future__ import annotations

import logging

import pandas as pd
from pydantic import BaseModel

from moex_dashboard.calc.funding import (
    build_funding_table,
    calc_d,
    calc_funding,
    funding_annualized,
    nearest_implied_rate,
    predicted_funding_sign,
    suggested_action,
)
from moex_dashboard.data.perpetual import (
    PERPETUAL_MAP,
    load_minute_candles,
    load_perpetual_prices,
    load_perpetual_specs,
)
from moex_dashboard.models import MarketSnapshot

logger = logging.getLogger(__name__)


class FundingResult(BaseModel):
    """Funding analysis result for one perpetual instrument."""
    name: str
    spot: float | None = None
    perp: float | None = None
    d: float | None = None
    quality: str = "insufficient"   # "full" / "partial" / "insufficient"
    l1: float | None = None
    l2: float | None = None
    funding: float | None = None
    funding_ann: float | None = None
    predicted: str = "0"            # "+fund" / "-fund" / "0"
    action: str = "NEUTRAL"         # "LONG" / "SHORT" / "NEUTRAL"
    implied_rate: float | None = None
    cash_rate: float | None = None
    funding_vs_cash: float | None = None
    implied_vs_cash: float | None = None


class FundingService:
    """Funding analysis for perpetual FX futures (USDRUBF, EURRUBF, CNYRUBF).

    Usage:
        svc = FundingService()
        results = svc.get_results(snapshot)      # list[FundingResult]
        df      = svc.get_table(snapshot)        # pd.DataFrame (display-ready)
        signals = svc.get_signals(snapshot)      # only instruments with clear signal
    """

    def get_results(self, snapshot: MarketSnapshot) -> list[FundingResult]:
        """Full funding analysis for all perpetuals.

        Loads data lazily on each call — caching is the caller's responsibility
        (Streamlit @st.cache_data, or service-level TTL cache).
        """
        try:
            perp_prices = load_perpetual_prices()
            perp_specs = load_perpetual_specs()
            candles_data = self._load_candles()
        except Exception:
            logger.exception("Failed to load perpetual data")
            return []

        results: list[FundingResult] = []
        for perp_secid, meta in PERPETUAL_MAP.items():
            spot_secid = meta["spot_secid"]
            name = meta["name"]
            divisor = meta["price_divisor"]

            spot_quote = snapshot.spots.get(spot_secid)
            if spot_quote is None or not spot_quote.price or spot_quote.price <= 0:
                results.append(FundingResult(name=name, quality="insufficient"))
                continue

            spot_price = spot_quote.price
            perp_price = perp_prices.get(perp_secid)

            spec = perp_specs.get(perp_secid, {})
            k1 = spec.get("k1", 0.0001)
            k2 = spec.get("k2", 0.001)
            l1 = k1 * spot_price
            l2 = k2 * spot_price

            candle_pair = candles_data.get(perp_secid, {})
            d_value, quality = calc_d(
                candle_pair.get("perp", pd.DataFrame()),
                candle_pair.get("spot", pd.DataFrame()),
                price_divisor=divisor,
            )

            funding_val = funding_ann = None
            pred_sign = 0
            action = "NEUTRAL"
            predicted = "0"

            if d_value is not None:
                funding_val = calc_funding(d_value, l1, l2)
                funding_ann = funding_annualized(funding_val, spot_price)
                pred_sign = predicted_funding_sign(d_value, l1)
                action = suggested_action(pred_sign)
                predicted = "+fund" if pred_sign > 0 else ("-fund" if pred_sign < 0 else "0")

            impl_rate_val = nearest_implied_rate(snapshot, perp_secid)
            cash_rate = snapshot.rusfar if snapshot.rusfar is not None else snapshot.key_rate

            results.append(FundingResult(
                name=name,
                spot=spot_price,
                perp=perp_price,
                d=d_value,
                quality=quality,
                l1=l1,
                l2=l2,
                funding=funding_val,
                funding_ann=funding_ann,
                predicted=predicted,
                action=action,
                implied_rate=impl_rate_val,
                cash_rate=cash_rate,
                funding_vs_cash=(funding_ann - cash_rate) if funding_ann is not None else None,
                implied_vs_cash=(impl_rate_val - cash_rate) if impl_rate_val is not None else None,
            ))

        return results

    def get_table(self, snapshot: MarketSnapshot) -> pd.DataFrame:
        """Return display-ready DataFrame (same schema as build_funding_table)."""
        try:
            perp_prices = load_perpetual_prices()
            perp_specs = load_perpetual_specs()
            candles_data = self._load_candles()
            return build_funding_table(snapshot, perp_prices, perp_specs, candles_data)
        except Exception:
            logger.exception("Failed to build funding table")
            return pd.DataFrame()

    def get_signals(self, snapshot: MarketSnapshot) -> list[FundingResult]:
        """Return only instruments with non-neutral action."""
        return [r for r in self.get_results(snapshot) if r.action != "NEUTRAL"]

    # -- Internal -----------------------------------------------------------

    def _load_candles(self) -> dict[str, dict[str, pd.DataFrame]]:
        """Load minute candles for all perpetuals. Returns empty DFs on failure."""
        candles: dict[str, dict[str, pd.DataFrame]] = {}
        for perp_secid, meta in PERPETUAL_MAP.items():
            spot_secid = meta["spot_secid"]
            try:
                perp_c = load_minute_candles(perp_secid, "futures", "forts")
                spot_c = load_minute_candles(spot_secid, "currency", "selt")
            except Exception:
                logger.warning("Candle load failed for %s", perp_secid)
                perp_c = pd.DataFrame()
                spot_c = pd.DataFrame()
            candles[perp_secid] = {"perp": perp_c, "spot": spot_c}
        return candles

