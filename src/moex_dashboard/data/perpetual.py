"""Load perpetual futures (eternal/forever futures) data from MOEX FORTS.

Perpetual FX futures (USDRUBF, EURRUBF, CNYRUBF) have a daily funding
mechanism that keeps their price close to the spot.  This module fetches
current prices, contract specifications (K1/K2), and intraday minute
candles needed for the funding calculation.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from moex_dashboard.data.moex_api import fetch_iss

# Perpetual ticker -> metadata for normalization and spot matching.
PERPETUAL_MAP: dict[str, dict] = {
    "USDRUBF": {
        "spot_secid": "USD000UTSTOM",
        "name": "USDRUB",
        "price_divisor": 1000,
    },
    "EURRUBF": {
        "spot_secid": "EUR_RUB__TOM",
        "name": "EURRUB",
        "price_divisor": 1000,
    },
    "CNYRUBF": {
        "spot_secid": "CNYRUB_TOM",
        "name": "CNYRUB",
        "price_divisor": 1,
    },
}

# Default K1/K2 values if the API does not expose them directly.
_DEFAULT_K1 = 0.0001
_DEFAULT_K2 = 0.001


def load_perpetual_prices() -> dict[str, float]:
    """Fetch current LAST price for each perpetual future.

    Uses the FORTS securities endpoint and filters by SECIDs defined in
    PERPETUAL_MAP.  Prices are normalized by the corresponding
    ``price_divisor`` so they are comparable to the spot (per-unit).

    Returns:
        Dict mapping perpetual SECID -> normalized price.
        Missing or zero prices are omitted.
    """
    perp_secids = list(PERPETUAL_MAP.keys())

    blocks = fetch_iss(
        "/engines/futures/markets/forts/securities.json",
        params={
            "iss.only": "securities,marketdata",
            "securities.columns": "SECID,SHORTNAME",
            "marketdata.columns": "SECID,LAST,SETTLEPRICE",
        },
    )

    if "marketdata" not in blocks:
        return {}

    md_df = blocks["marketdata"]
    md_df = md_df[md_df["SECID"].isin(perp_secids)]

    result: dict[str, float] = {}
    for _, row in md_df.iterrows():
        secid = row["SECID"]
        price = row["LAST"]
        if price is None or (isinstance(price, (int, float)) and price <= 0):
            price = row.get("SETTLEPRICE")
        if price is None or (isinstance(price, (int, float)) and price <= 0):
            continue

        divisor = PERPETUAL_MAP[secid]["price_divisor"]
        result[secid] = float(price) / divisor

    return result


def load_perpetual_specs() -> dict[str, dict]:
    """Fetch K1, K2, and lot size for each perpetual contract.

    Queries the individual security description endpoint for each ticker.
    If K1/K2 columns are not present in the API response, falls back to
    sensible defaults (_DEFAULT_K1, _DEFAULT_K2).

    Returns:
        Dict mapping perpetual SECID -> {"k1": float, "k2": float, "lotsize": int}.
    """
    result: dict[str, dict] = {}

    for secid in PERPETUAL_MAP:
        try:
            blocks = fetch_iss(
                f"/engines/futures/markets/forts/securities/{secid}.json",
                params={"iss.only": "securities"},
            )
        except Exception:
            # Graceful degradation: use defaults if the request fails.
            result[secid] = {
                "k1": _DEFAULT_K1,
                "k2": _DEFAULT_K2,
                "lotsize": _guess_lotsize(secid),
            }
            continue

        if "securities" not in blocks or blocks["securities"].empty:
            result[secid] = {
                "k1": _DEFAULT_K1,
                "k2": _DEFAULT_K2,
                "lotsize": _guess_lotsize(secid),
            }
            continue

        sec_df = blocks["securities"]
        row = sec_df.iloc[0]

        # Try to extract K1 / K2 from known column names.
        k1 = _extract_float(row, ["K1", "SWAPRATE1", "FUNDINGRATE1"])
        k2 = _extract_float(row, ["K2", "SWAPRATE2", "FUNDINGRATE2"])

        if k1 is None:
            k1 = _DEFAULT_K1
        if k2 is None:
            k2 = _DEFAULT_K2

        # Lot size — LOTVOLUME or LOTSIZE column.
        lotsize = _extract_int(row, ["LOTVOLUME", "LOTSIZE"])
        if lotsize is None or lotsize <= 0:
            lotsize = _guess_lotsize(secid)

        result[secid] = {"k1": k1, "k2": k2, "lotsize": lotsize}

    return result


def load_minute_candles(
    secid: str,
    engine: str,
    market: str,
    trading_date: date | None = None,
) -> pd.DataFrame:
    """Fetch today's 1-minute candles for the given security.

    Args:
        secid: Instrument ticker (e.g. "USDRUBF" or "USD000UTSTOM").
        engine: ISS engine (e.g. "futures" or "currency").
        market: ISS market (e.g. "forts" or "selt").
        trading_date: Date for which to load candles (default: today).

    Returns:
        DataFrame with at least columns ``begin`` (datetime) and ``close``
        (float).  Empty DataFrame if the endpoint returns no data.
    """
    if trading_date is None:
        trading_date = date.today()

    date_str = trading_date.isoformat()

    all_rows: list[pd.DataFrame] = []
    start = 0

    while True:
        params: dict = {
            "interval": 1,
            "from": date_str,
            "till": date_str,
            "iss.only": "candles",
            "candles.columns": "begin,close",
            "start": start,
        }

        blocks = fetch_iss(
            f"/engines/{engine}/markets/{market}/securities/{secid}/candles.json",
            params=params,
        )

        if "candles" not in blocks:
            break

        chunk = blocks["candles"]
        if chunk.empty:
            break

        all_rows.append(chunk)

        # ISS pagination: if we received a full page (500 rows is the
        # typical MOEX page size), there might be more data.
        if len(chunk) < 500:
            break
        start += len(chunk)

    if not all_rows:
        return pd.DataFrame(columns=["begin", "close"])

    df = pd.concat(all_rows, ignore_index=True)

    # Parse begin timestamp and ensure close is numeric.
    df["begin"] = pd.to_datetime(df["begin"], errors="coerce")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df.dropna(subset=["begin", "close"], inplace=True)
    df.sort_values("begin", inplace=True)
    df.reset_index(drop=True, inplace=True)

    return df


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_float(row: pd.Series, candidates: list[str]) -> float | None:
    """Try to read a float value from the first matching column in *row*."""
    for col in candidates:
        if col in row.index:
            val = row[col]
            if val is not None:
                try:
                    fval = float(val)
                    if fval > 0:
                        return fval
                except (ValueError, TypeError):
                    continue
    return None


def _extract_int(row: pd.Series, candidates: list[str]) -> int | None:
    """Try to read an int value from the first matching column in *row*."""
    for col in candidates:
        if col in row.index:
            val = row[col]
            if val is not None:
                try:
                    return int(val)
                except (ValueError, TypeError):
                    continue
    return None


def _guess_lotsize(secid: str) -> int:
    """Return a sensible default lot size based on the ticker.

    USDRUBF and EURRUBF have lot = 1000 (USD/EUR per contract).
    CNYRUBF has lot = 1000 (CNY per contract).
    """
    return 1000
