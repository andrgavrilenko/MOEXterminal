"""CIP (Covered Interest Parity) and cross-currency calculations."""


def implied_usdcny(si_price: float, cr_price: float) -> float | None:
    """Implied USDCNY from Si and CR futures of the same expiry.

    Formula: Si / CR
    """
    if cr_price <= 0:
        return None
    return si_price / cr_price


def forward_premium(
    implied_cross: float, spot_cross: float, days: int
) -> float | None:
    """Annualized forward premium of an implied cross vs spot.

    Formula: (impl / spot - 1) * 365 / days
    """
    if days <= 0 or spot_cross <= 0:
        return None
    return (implied_cross / spot_cross - 1) * 365 / days


def si_parity(cnyrub: float, usdcny: float) -> float:
    """Fair USDRUB from the CNY triangle.

    Formula: CNYRUB * USDCNY
    """
    return cnyrub * usdcny


def eu_parity(usdrub: float, eurusd: float) -> float:
    """Fair EURRUB from the USD/EUR triangle.

    Formula: USDRUB * EURUSD
    """
    return usdrub * eurusd


def gold_parity(gd_price_usd: float, usdrub: float) -> float:
    """Fair gold price in RUB per gram.

    GL_fair = GD_price * USDRUB / 31.1035
    """
    return gd_price_usd * usdrub / 31.1035


def gold_deviation(gl_market: float, gl_fair: float) -> float | None:
    """Deviation of market gold RUB vs fair value.

    Returns fraction: GL_market / GL_fair - 1
    """
    if gl_fair <= 0:
        return None
    return gl_market / gl_fair - 1


def cross_instrument_spread(price_a: float, price_b: float) -> float | None:
    """Spread between two instruments tracking the same underlying.

    Returns fraction: price_a / price_b - 1
    """
    if price_b <= 0:
        return None
    return price_a / price_b - 1
