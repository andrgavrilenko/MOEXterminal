"""Calculation layer: arbitrage formulas and pipeline builders."""

from .arbitrage import basis, carry_premium, daily_carry, fair_value, implied_rate
from .cip import (
    cross_instrument_spread,
    eu_parity,
    forward_premium,
    gold_deviation,
    gold_parity,
    implied_usdcny,
    si_parity,
)
from .pipeline import (
    build_arbitrage_table,
    build_cip_table,
    build_cross_gold_table,
    build_cross_instrument_table,
    build_curves_table,
    build_stocks_table,
)
from .funding import (
    build_funding_table,
    calc_d,
    calc_funding,
    funding_annualized,
    predicted_funding_sign,
    suggested_action,
)
from .stocks import dividend_yield, implied_dividend

__all__ = [
    # arbitrage
    "implied_rate",
    "fair_value",
    "carry_premium",
    "basis",
    "daily_carry",
    # cip
    "implied_usdcny",
    "forward_premium",
    "si_parity",
    "eu_parity",
    "gold_parity",
    "gold_deviation",
    "cross_instrument_spread",
    # stocks
    "implied_dividend",
    "dividend_yield",
    # funding
    "calc_d",
    "calc_funding",
    "predicted_funding_sign",
    "suggested_action",
    "funding_annualized",
    "build_funding_table",
    # pipeline
    "build_arbitrage_table",
    "build_cip_table",
    "build_cross_gold_table",
    "build_cross_instrument_table",
    "build_curves_table",
    "build_stocks_table",
]
