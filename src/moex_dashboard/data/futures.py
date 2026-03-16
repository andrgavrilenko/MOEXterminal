"""Load futures contracts from MOEX FORTS market."""

from datetime import date, datetime

import pandas as pd

from moex_dashboard.config import ASSET_MAP
from moex_dashboard.data.moex_api import fetch_iss
from moex_dashboard.models import FuturesContract


def load_all_futures() -> dict[str, list[FuturesContract]]:
    """Fetch all futures from FORTS, filter by ASSET_MAP, return grouped by asset_code.

    Returns:
        Dict asset_code -> list of FuturesContract sorted by expiry_date.
        Only includes contracts with days_to_expiry > 0 and a valid price.
    """
    blocks = fetch_iss(
        "/engines/futures/markets/forts/securities.json",
        params={
            "iss.only": "securities,marketdata",
            "securities.columns": "SECID,SHORTNAME,LASTDELDATE,ASSETCODE",
            "marketdata.columns": "SECID,LAST,SETTLEPRICE",
        },
    )

    if "securities" not in blocks or "marketdata" not in blocks:
        return {}

    sec_df = blocks["securities"]
    md_df = blocks["marketdata"]

    # Merge on SECID
    merged = pd.merge(sec_df, md_df, on="SECID", how="inner")

    # Filter to tracked asset codes
    tracked_codes = set(ASSET_MAP.keys())
    merged = merged[merged["ASSETCODE"].isin(tracked_codes)]

    today = date.today()
    result: dict[str, list[FuturesContract]] = {}

    for _, row in merged.iterrows():
        asset_code = row["ASSETCODE"]
        secid = row["SECID"]

        # Parse expiry date
        expiry = _parse_expiry(row["LASTDELDATE"])
        if expiry is None:
            continue

        days = (expiry - today).days
        if days <= 0:
            continue

        # Get price: prefer LAST, fall back to SETTLEPRICE
        price = row["LAST"]
        if price is None or (isinstance(price, float) and price <= 0):
            price = row["SETTLEPRICE"]
        if price is None or (isinstance(price, float) and price <= 0):
            continue

        # Normalize price to per-unit (comparable to spot)
        divisor = ASSET_MAP[asset_code].get("price_divisor", 1)
        normalized_price = float(price) / divisor

        contract = FuturesContract(
            secid=secid,
            asset_code=asset_code,
            expiry_date=expiry,
            price=normalized_price,
            days_to_expiry=days,
        )

        result.setdefault(asset_code, []).append(contract)

    # Sort each group by expiry
    for code in result:
        result[code].sort(key=lambda c: c.expiry_date)

    return result


def _parse_expiry(value) -> date | None:
    """Parse LASTDELDATE which can be 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM:SS'."""
    if value is None:
        return None
    try:
        if isinstance(value, date):
            return value
        s = str(value).strip()
        if " " in s:
            return datetime.strptime(s.split(" ")[0], "%Y-%m-%d").date()
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
