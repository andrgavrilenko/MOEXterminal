"""Load interest rates: RUSFAR from MOEX, КС ЦБ from config."""

from moex_dashboard.config import KEY_RATE
from moex_dashboard.data.moex_api import fetch_iss


def load_rusfar() -> float | None:
    """Fetch current RUSFAR rate from MOEX index.

    Returns:
        RUSFAR as a fraction (e.g. 0.1515 for 15.15%), or None if unavailable.
    """
    try:
        blocks = fetch_iss(
            "/engines/stock/markets/index/securities/RUSFAR.json",
            params={
                "iss.only": "marketdata",
                "marketdata.columns": "SECID,CURRENTVALUE",
            },
        )

        if "marketdata" in blocks:
            df = blocks["marketdata"]
            if not df.empty:
                value = df.iloc[0]["CURRENTVALUE"]
                if value is not None and value > 0:
                    return float(value) / 100  # Convert from 15.15 to 0.1515
    except Exception:
        pass

    return None


def get_key_rate() -> float:
    """Return the current КС ЦБ from config.

    This is hardcoded because CBR doesn't expose a reliable free API.
    Update KEY_RATE in config.py when the rate changes.
    """
    return KEY_RATE
