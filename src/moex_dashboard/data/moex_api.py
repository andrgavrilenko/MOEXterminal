"""MOEX ISS API wrapper — fetch and parse JSON responses into DataFrames."""

import time

import pandas as pd
import requests

from moex_dashboard.config import BASE_URL, MAX_RETRIES, REQUEST_TIMEOUT


def fetch_iss(endpoint: str, params: dict | None = None) -> dict[str, pd.DataFrame]:
    """Fetch data from MOEX ISS API and parse all blocks into DataFrames.

    Args:
        endpoint: API path after base URL (e.g. "/engines/currency/markets/selt/...")
        params: Query parameters

    Returns:
        Dict of block_name -> DataFrame (e.g. {"marketdata": df, "securities": df})

    Raises:
        requests.RequestException: After MAX_RETRIES failed attempts.
    """
    url = f"{BASE_URL}{endpoint}"
    if params is None:
        params = {}
    params["iss.meta"] = "off"

    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            return _parse_iss_response(data)
        except (requests.RequestException, ValueError) as e:
            last_error = e
            if attempt < MAX_RETRIES:
                time.sleep(1)

    raise last_error  # type: ignore[misc]


def _parse_iss_response(data: dict) -> dict[str, pd.DataFrame]:
    """Parse ISS JSON response into dict of DataFrames.

    ISS returns blocks like:
        [{"charsetinfo": ...}, {"marketdata": {"columns": [...], "data": [...]}}]
    or:
        {"marketdata": {"columns": [...], "data": [...]}}
    """
    result = {}

    # Handle extended format: list of dicts
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                for key, value in item.items():
                    if isinstance(value, dict) and "columns" in value and "data" in value:
                        result[key] = pd.DataFrame(value["data"], columns=value["columns"])
    elif isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, dict) and "columns" in value and "data" in value:
                result[key] = pd.DataFrame(value["data"], columns=value["columns"])

    return result
