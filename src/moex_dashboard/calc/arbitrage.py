"""Core arbitrage calculations: implied rate, fair value, basis, carry."""


def implied_rate(futures_price: float, spot_price: float, days: int) -> float | None:
    """Annualized implied rate from futures/spot ratio.

    Formula: (F/S - 1) * 365 / days
    """
    if days <= 0 or spot_price <= 0:
        return None
    return (futures_price / spot_price - 1) * 365 / days


def fair_value(spot_price: float, rate: float, days: int) -> float:
    """Theoretical futures price at a given interest rate.

    Formula: S * (1 + rate * days / 365)
    """
    return spot_price * (1 + rate * days / 365)


def carry_premium(impl_rate: float, benchmark_rate: float) -> float:
    """Extra return over a benchmark (KS or RUSFAR).

    Formula: implied - benchmark
    """
    return impl_rate - benchmark_rate


def basis(futures_price: float, spot_price: float) -> float:
    """Absolute basis (contango > 0, backwardation < 0).

    Formula: F - S
    """
    return futures_price - spot_price


def daily_carry(futures_price: float, spot_price: float, days: int) -> float | None:
    """Annualized basis per day — equivalent to implied_rate.

    Formula: (F - S) / S / days * 365
    """
    if days <= 0 or spot_price <= 0:
        return None
    return (futures_price - spot_price) / spot_price / days * 365
