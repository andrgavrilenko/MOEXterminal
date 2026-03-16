"""Load spot prices: currencies and indices from MOEX ISS."""

from moex_dashboard.config import (
    SPOT_CURRENCIES,
    SPOT_INDICES,
    SPOT_NAMES,
    STOCK_SECURITIES,
)
from moex_dashboard.data.moex_api import fetch_iss
from moex_dashboard.models import SpotQuote


def load_spot_currencies() -> dict[str, SpotQuote]:
    """Fetch spot currency prices (USDRUB, CNYRUB, EURRUB).

    Returns:
        Dict secid -> SpotQuote with LAST price.
    """
    securities = ",".join(SPOT_CURRENCIES)
    blocks = fetch_iss(
        "/engines/currency/markets/selt/boards/CETS/securities.json",
        params={
            "iss.only": "marketdata",
            "marketdata.columns": "SECID,LAST",
            "securities": securities,
        },
    )

    result = {}
    if "marketdata" in blocks:
        df = blocks["marketdata"]
        for _, row in df.iterrows():
            secid = row["SECID"]
            price = row["LAST"]
            if price is not None and price > 0:
                result[secid] = SpotQuote(
                    secid=secid,
                    name=SPOT_NAMES.get(secid, secid),
                    price=float(price),
                )
    return result


def load_indices() -> dict[str, SpotQuote]:
    """Fetch index values (IMOEX, RTSI).

    Returns:
        Dict secid -> SpotQuote with CURRENTVALUE.
    """
    securities = ",".join(SPOT_INDICES)
    blocks = fetch_iss(
        "/engines/stock/markets/index/securities.json",
        params={
            "iss.only": "marketdata",
            "marketdata.columns": "SECID,CURRENTVALUE",
            "securities": securities,
        },
    )

    result = {}
    if "marketdata" in blocks:
        df = blocks["marketdata"]
        for _, row in df.iterrows():
            secid = row["SECID"]
            price = row["CURRENTVALUE"]
            if price is not None and price > 0:
                result[secid] = SpotQuote(
                    secid=secid,
                    name=SPOT_NAMES.get(secid, secid),
                    price=float(price),
                )
    return result


def load_stock_spots() -> dict[str, SpotQuote]:
    """Fetch stock spot prices from TQBR board (Сбербанк, Газпром, etc.).

    Returns:
        Dict secid -> SpotQuote with LAST price.
    """
    if not STOCK_SECURITIES:
        return {}

    securities = ",".join(STOCK_SECURITIES)
    blocks = fetch_iss(
        "/engines/stock/markets/shares/boards/TQBR/securities.json",
        params={
            "iss.only": "marketdata",
            "marketdata.columns": "SECID,LAST",
            "securities": securities,
        },
    )

    result = {}
    if "marketdata" in blocks:
        df = blocks["marketdata"]
        for _, row in df.iterrows():
            secid = row["SECID"]
            price = row["LAST"]
            if price is not None and price > 0:
                result[secid] = SpotQuote(
                    secid=secid,
                    name=SPOT_NAMES.get(secid, secid),
                    price=float(price),
                )
    return result
