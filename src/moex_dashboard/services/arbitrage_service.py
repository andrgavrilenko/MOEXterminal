"""Arbitrage Service — all arbitrage strategies in one place.

Wraps calc/pipeline + calc/cip + inline UI logic into service methods.
Each method takes a MarketSnapshot and returns a ready DataFrame or dict.

Subdomains:
- Cash-and-Carry / Reverse C&C
- Calendar FX spreads
- Cross-FX (triangle parity)
- Cross-Gold (GD vs GL)
- Cross-Instrument (MIX/MXI, RTS/RTSM)
- CIP Arb (implied USDCNY)

Funding is NOT here — it will be a separate funding_service (Phase 4).
"""

from __future__ import annotations

import pandas as pd
from pydantic import BaseModel

from moex_dashboard.calc.cip import eu_parity, si_parity
from moex_dashboard.calc.pipeline import (
    build_arbitrage_table,
    build_cip_table,
    build_cross_gold_table,
    build_cross_instrument_table,
)
from moex_dashboard.config import ASSET_MAP
from moex_dashboard.models import MarketSnapshot


class CrossFxResult(BaseModel):
    """Triangle parity check for USDRUB and EURRUB."""
    fair_si: float          # CNYRUB * USDCNY
    actual_si: float        # market USDRUB
    si_deviation_pct: float
    fair_eu: float          # USDRUB * EURUSD
    actual_eu: float        # market EURRUB
    eu_deviation_pct: float
    spot_usdcny: float
    spot_eurusd: float


class ArbitrageService:
    """Stateless service — all data comes from the snapshot argument."""

    # -- Cash-and-Carry (currencies + indices only) -------------------------

    def get_cash_and_carry(self, snapshot: MarketSnapshot) -> pd.DataFrame:
        """Implied rate table filtered to currencies and indices."""
        df = build_arbitrage_table(snapshot)
        if df.empty:
            return df

        currency_index_names = {
            v["name"] for v in ASSET_MAP.values()
            if v.get("market") in ("currency", "index")
        }
        df = df[df["Актив"].isin(currency_index_names)].copy()
        df.reset_index(drop=True, inplace=True)
        return df

    # -- Reverse Cash-and-Carry ---------------------------------------------

    def get_reverse_cc(self, snapshot: MarketSnapshot) -> pd.DataFrame:
        """Contracts where implied rate < key rate (backwardation = opportunity)."""
        df = build_arbitrage_table(snapshot)
        if df.empty:
            return df

        reverse = df[df["Implied Rate"] < snapshot.key_rate].copy()
        if reverse.empty:
            return reverse

        reverse["Potential Profit"] = reverse["Премия к КС"].abs()
        reverse.reset_index(drop=True, inplace=True)
        return reverse

    # -- Calendar FX --------------------------------------------------------

    def get_calendar_fx(self, snapshot: MarketSnapshot) -> pd.DataFrame:
        """Near/far implied rate spreads for FX futures."""
        df = build_arbitrage_table(snapshot)
        if df.empty:
            return pd.DataFrame()

        fx_names = {
            v["name"] for v in ASSET_MAP.values()
            if v.get("market") == "currency"
        }
        df = df[df["Актив"].isin(fx_names)].copy()
        if df.empty:
            return pd.DataFrame()

        rows: list[dict] = []
        for asset_name, group in df.groupby("Актив"):
            group = group.sort_values("Дней")
            contracts = group.to_dict("records")
            for i in range(len(contracts) - 1):
                near = contracts[i]
                far = contracts[i + 1]
                delta_days = far["Дней"] - near["Дней"]
                if delta_days <= 0:
                    continue
                fwd_rate = (
                    (far["Фьюч"] / near["Фьюч"] - 1) * 365 / delta_days
                    if near["Фьюч"] > 0 else None
                )
                rate_diff = far["Implied Rate"] - near["Implied Rate"]
                rows.append({
                    "Актив": asset_name,
                    "Ближний": near["Контракт"],
                    "Дальний": far["Контракт"],
                    "Дней (спред)": delta_days,
                    "Fwd Rate": fwd_rate,
                    "Rate Diff": rate_diff,
                })

        return pd.DataFrame(rows)

    # -- Cross-FX (triangle parity) -----------------------------------------

    def get_cross_fx(self, snapshot: MarketSnapshot) -> CrossFxResult | None:
        """Check USDRUB and EURRUB triangle parity vs CNYRUB."""
        usdrub = snapshot.spots.get("USD000UTSTOM")
        cnyrub = snapshot.spots.get("CNYRUB_TOM")
        eurrub = snapshot.spots.get("EUR_RUB__TOM")

        if not usdrub or not cnyrub or not eurrub:
            return None
        if cnyrub.price <= 0 or usdrub.price <= 0:
            return None

        spot_usdcny = usdrub.price / cnyrub.price
        spot_eurusd = eurrub.price / usdrub.price

        fair_si = si_parity(cnyrub.price, spot_usdcny)
        si_dev = (usdrub.price / fair_si - 1) * 100 if fair_si > 0 else 0.0

        fair_eu = eu_parity(usdrub.price, spot_eurusd)
        eu_dev = (eurrub.price / fair_eu - 1) * 100 if fair_eu > 0 else 0.0

        return CrossFxResult(
            fair_si=fair_si,
            actual_si=usdrub.price,
            si_deviation_pct=si_dev,
            fair_eu=fair_eu,
            actual_eu=eurrub.price,
            eu_deviation_pct=eu_dev,
            spot_usdcny=spot_usdcny,
            spot_eurusd=spot_eurusd,
        )

    # -- Cross-Gold ---------------------------------------------------------

    def get_cross_gold(self, snapshot: MarketSnapshot) -> pd.DataFrame:
        return build_cross_gold_table(snapshot)

    # -- Cross-Instrument ---------------------------------------------------

    def get_cross_instrument(self, snapshot: MarketSnapshot) -> pd.DataFrame:
        return build_cross_instrument_table(snapshot)

    # -- CIP Arb ------------------------------------------------------------

    def get_cip(self, snapshot: MarketSnapshot) -> pd.DataFrame:
        return build_cip_table(snapshot)
