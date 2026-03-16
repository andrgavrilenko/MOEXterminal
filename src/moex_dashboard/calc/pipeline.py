"""Build display-ready DataFrames from a MarketSnapshot."""

from __future__ import annotations

import pandas as pd

from ..config import ASSET_MAP
from ..models import MarketSnapshot
from . import arbitrage, cip, stocks

# Cross-instrument pairs: (asset_code_a, asset_code_b, underlying_name)
_CROSS_INSTRUMENT_PAIRS = [
    ("MIX", "MXI", "IMOEX"),
    ("RTS", "RTSM", "RTSI"),
]


def build_arbitrage_table(snapshot: MarketSnapshot) -> pd.DataFrame:
    """One row per futures contract with implied rate and premiums."""
    rows: list[dict] = []
    for asset_code, contracts in snapshot.futures.items():
        mapping = ASSET_MAP.get(asset_code)
        if mapping is None:
            continue
        spot_secid = mapping["spot_secid"]
        spot_quote = snapshot.spots.get(spot_secid)
        if spot_quote is None or spot_quote.price is None:
            continue
        spot_price = spot_quote.price
        for fc in contracts:
            if fc.price is None or fc.days_to_expiry <= 0:
                continue
            impl = arbitrage.implied_rate(fc.price, spot_price, fc.days_to_expiry)
            if impl is None:
                continue
            premium_ks = arbitrage.carry_premium(impl, snapshot.key_rate)
            premium_rusfar = (
                arbitrage.carry_premium(impl, snapshot.rusfar)
                if snapshot.rusfar is not None
                else None
            )
            rows.append(
                {
                    "Актив": mapping["name"],
                    "Контракт": fc.secid,
                    "Экспирация": fc.expiry_date,
                    "Дней": fc.days_to_expiry,
                    "Спот": spot_price,
                    "Фьюч": fc.price,
                    "Базис": arbitrage.basis(fc.price, spot_price),
                    "Implied Rate": impl,
                    "Премия к КС": premium_ks,
                    "Премия к RUSFAR": premium_rusfar,
                }
            )
    df = pd.DataFrame(rows)
    if not df.empty:
        df.sort_values(["Актив", "Дней"], inplace=True)
        df.reset_index(drop=True, inplace=True)
    return df


def build_cip_table(snapshot: MarketSnapshot) -> pd.DataFrame:
    """CIP table: implied USDCNY from Si/CR pairs, forward premium."""
    si_contracts = snapshot.futures.get("Si", [])
    # MOEX ASSETCODE for CNYRUB futures is "CR"; fall back to "CNY" if needed
    cr_contracts = snapshot.futures.get("CR", []) or snapshot.futures.get("CNY", [])
    if not si_contracts or not cr_contracts:
        return pd.DataFrame()

    # Spot USDCNY from spot quotes
    usdrub_quote = snapshot.spots.get("USD000UTSTOM")
    cnyrub_quote = snapshot.spots.get("CNYRUB_TOM")
    if (
        usdrub_quote is None
        or cnyrub_quote is None
        or usdrub_quote.price is None
        or cnyrub_quote.price is None
        or cnyrub_quote.price <= 0
    ):
        return pd.DataFrame()

    spot_usdcny = usdrub_quote.price / cnyrub_quote.price

    # Match Si and CR by expiry date
    cr_by_expiry = {c.expiry_date: c for c in cr_contracts if c.price is not None}

    rows: list[dict] = []
    for si in si_contracts:
        if si.price is None or si.days_to_expiry <= 0:
            continue
        cr = cr_by_expiry.get(si.expiry_date)
        if cr is None or cr.price is None:
            continue
        impl = cip.implied_usdcny(si.price, cr.price)
        if impl is None:
            continue
        fwd_prem = cip.forward_premium(impl, spot_usdcny, si.days_to_expiry)
        rows.append(
            {
                "Экспирация": si.expiry_date,
                "Дней": si.days_to_expiry,
                "Si (USDRUB)": si.price,
                "CR (CNYRUB)": cr.price,
                "Impl. USDCNY": impl,
                "Spot USDCNY": spot_usdcny,
                "Fwd Premium": fwd_prem,
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df.sort_values("Дней", inplace=True)
        df.reset_index(drop=True, inplace=True)
    return df


def build_curves_table(
    snapshot: MarketSnapshot, asset_code: str
) -> pd.DataFrame:
    """Per-asset curve: all contracts with implied rate and premium.

    For assets with a spot (currencies, indices, stocks): implied rate vs spot.
    For commodities (no spot): implied rate vs front (nearest) contract per TZ 7.3.
    """
    contracts = snapshot.futures.get(asset_code, [])
    if not contracts:
        return pd.DataFrame()

    mapping = ASSET_MAP.get(asset_code)
    if mapping is None:
        return pd.DataFrame()

    valid = [c for c in contracts if c.price is not None and c.days_to_expiry > 0]
    if not valid:
        return pd.DataFrame()
    valid.sort(key=lambda c: c.days_to_expiry)

    is_commodity = mapping.get("market") == "commodity" or mapping.get("spot_secid") is None

    if is_commodity:
        # Commodities: use front contract as base
        front = valid[0]
        base_price = front.price
        base_label = f"{front.secid} (front)"
        calc_contracts = valid[1:]  # skip front itself
    else:
        spot_secid = mapping["spot_secid"]
        spot_quote = snapshot.spots.get(spot_secid)
        if spot_quote is None or spot_quote.price is None:
            return pd.DataFrame()
        base_price = spot_quote.price
        base_label = "Spot"
        calc_contracts = valid

    rows: list[dict] = []
    for fc in calc_contracts:
        if is_commodity:
            # Days difference from front, not from today
            delta_days = fc.days_to_expiry - valid[0].days_to_expiry
            if delta_days <= 0:
                continue
            impl = arbitrage.implied_rate(fc.price, base_price, delta_days)
        else:
            impl = arbitrage.implied_rate(fc.price, base_price, fc.days_to_expiry)

        if impl is None:
            continue
        premium_ks = arbitrage.carry_premium(impl, snapshot.key_rate)
        rows.append(
            {
                "Фьючерс": fc.secid,
                "Экспирация": fc.expiry_date,
                "Дней": fc.days_to_expiry,
                "Цена": fc.price,
                "База": base_price,
                "Тип базы": base_label,
                "Implied Rate": impl,
                "Премия к КС": premium_ks,
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df.sort_values("Дней", inplace=True)
        df.reset_index(drop=True, inplace=True)
    return df


def build_stocks_table(snapshot: MarketSnapshot) -> pd.DataFrame:
    """Stocks summary: nearest/farthest futures, implied dividends."""
    rows: list[dict] = []
    for asset_code, contracts in snapshot.futures.items():
        mapping = ASSET_MAP.get(asset_code)
        if mapping is None:
            continue
        # Only stock assets have market == "stock"
        if mapping.get("market") != "stock":
            continue
        spot_secid = mapping["spot_secid"]
        spot_quote = snapshot.spots.get(spot_secid)
        if spot_quote is None or spot_quote.price is None:
            continue
        spot_price = spot_quote.price

        # Filter to contracts with valid prices
        valid = [c for c in contracts if c.price is not None and c.days_to_expiry > 0]
        if not valid:
            continue
        valid.sort(key=lambda c: c.days_to_expiry)
        front = valid[0]
        back = valid[-1]

        front_impl = arbitrage.implied_rate(
            front.price, spot_price, front.days_to_expiry
        )
        back_impl = arbitrage.implied_rate(
            back.price, spot_price, back.days_to_expiry
        )

        # Implied dividend from farthest contract
        div_impl = stocks.implied_dividend(
            spot_price, back.price, snapshot.key_rate, back.days_to_expiry
        )
        div_yld = stocks.dividend_yield(div_impl, spot_price)

        rows.append(
            {
                "Актив": mapping["name"],
                "Тикер": spot_secid,
                "Спот": spot_price,
                "Контр.": len(valid),
                "Ближний": front.secid,
                "Ближн.цена": front.price,
                "Ближн.rate": front_impl,
                "Дальний": back.secid,
                "Дальн.цена": back.price,
                "Дальн.rate": back_impl,
                "Div руб.": div_impl,
                "Div %": div_yld,
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df.sort_values("Актив", inplace=True)
        df.reset_index(drop=True, inplace=True)
    return df


def build_cross_gold_table(snapshot: MarketSnapshot) -> pd.DataFrame:
    """Cross-Gold: compare GD (gold USD) vs GL (gold RUB) for same expiry.

    For each matching expiry pair:
    - GL_fair = GD_price * USDRUB / 31.1035
    - Deviation = GL_market / GL_fair - 1
    Need USDRUB spot from snapshot.
    """
    gd_contracts = snapshot.futures.get("GD", [])
    gl_contracts = snapshot.futures.get("GL", [])
    if not gd_contracts or not gl_contracts:
        return pd.DataFrame()

    # Need USDRUB spot to convert GD (USD) to RUB
    usdrub_quote = snapshot.spots.get("USD000UTSTOM")
    if usdrub_quote is None or usdrub_quote.price is None or usdrub_quote.price <= 0:
        return pd.DataFrame()
    usdrub = usdrub_quote.price

    # Index GL contracts by expiry date
    gl_by_expiry = {c.expiry_date: c for c in gl_contracts if c.price is not None}

    rows: list[dict] = []
    for gd in gd_contracts:
        if gd.price is None or gd.days_to_expiry <= 0:
            continue
        gl = gl_by_expiry.get(gd.expiry_date)
        if gl is None or gl.price is None:
            continue

        gl_fair = cip.gold_parity(gd.price, usdrub)
        deviation = cip.gold_deviation(gl.price, gl_fair)

        rows.append(
            {
                "Экспирация": gd.expiry_date,
                "Дней": gd.days_to_expiry,
                "GD (USD)": gd.price,
                "GL (RUB)": gl.price,
                "USDRUB": usdrub,
                "GL Fair": gl_fair,
                "Deviation": deviation,
            }
        )

    df = pd.DataFrame(rows)
    if not df.empty:
        df.sort_values("Дней", inplace=True)
        df.reset_index(drop=True, inplace=True)
    return df


def build_cross_instrument_table(snapshot: MarketSnapshot) -> pd.DataFrame:
    """Cross-Instrument: compare related futures pairs.

    Pairs: MIX vs MXI (both IMOEX), RTS vs RTSM (both RTSI)
    For each matching expiry:
    - Spread = price_a / price_b - 1
    - Implied rate difference
    """
    rows: list[dict] = []

    for code_a, code_b, underlying in _CROSS_INSTRUMENT_PAIRS:
        contracts_a = snapshot.futures.get(code_a, [])
        contracts_b = snapshot.futures.get(code_b, [])
        if not contracts_a or not contracts_b:
            continue

        mapping_a = ASSET_MAP.get(code_a)
        mapping_b = ASSET_MAP.get(code_b)
        if mapping_a is None or mapping_b is None:
            continue

        # Get spot price for implied rate calculation
        spot_secid = mapping_a.get("spot_secid")
        spot_price: float | None = None
        if spot_secid:
            spot_quote = snapshot.spots.get(spot_secid)
            if spot_quote is not None and spot_quote.price is not None:
                spot_price = spot_quote.price

        # Index B contracts by expiry
        b_by_expiry = {c.expiry_date: c for c in contracts_b if c.price is not None}

        for ca in contracts_a:
            if ca.price is None or ca.days_to_expiry <= 0:
                continue
            cb = b_by_expiry.get(ca.expiry_date)
            if cb is None or cb.price is None:
                continue

            spread = cip.cross_instrument_spread(ca.price, cb.price)

            # Implied rates vs spot (if available)
            rate_a: float | None = None
            rate_b: float | None = None
            rate_diff: float | None = None
            if spot_price is not None and spot_price > 0:
                rate_a = arbitrage.implied_rate(
                    ca.price, spot_price, ca.days_to_expiry
                )
                rate_b = arbitrage.implied_rate(
                    cb.price, spot_price, cb.days_to_expiry
                )
                if rate_a is not None and rate_b is not None:
                    rate_diff = rate_a - rate_b

            rows.append(
                {
                    "Underlying": underlying,
                    "Экспирация": ca.expiry_date,
                    "Дней": ca.days_to_expiry,
                    f"{code_a}": ca.price,
                    f"{code_b}": cb.price,
                    "Spread": spread,
                    f"Rate {code_a}": rate_a,
                    f"Rate {code_b}": rate_b,
                    "Rate Diff": rate_diff,
                }
            )

    df = pd.DataFrame(rows)
    if not df.empty:
        df.sort_values(["Underlying", "Дней"], inplace=True)
        df.reset_index(drop=True, inplace=True)
    return df
