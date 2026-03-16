"""Stock-specific calculations: implied dividends and yields."""

from .arbitrage import fair_value


def implied_dividend(
    spot_price: float, futures_price: float, rate: float, days: int
) -> float:
    """Expected dividend implied by the futures discount.

    Formula: fair_value(spot, rate, days) - futures
    """
    fv = fair_value(spot_price, rate, days)
    return fv - futures_price


def dividend_yield(implied_div: float, spot_price: float) -> float | None:
    """Dividend yield as a fraction of spot price.

    Formula: implied_div / spot
    """
    if spot_price <= 0:
        return None
    return implied_div / spot_price
