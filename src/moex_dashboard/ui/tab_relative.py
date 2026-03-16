"""Tab: Relative Value — Curve Shape, Calendar Commodity, Rate Spread."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ..calc import implied_rate, carry_premium
from ..config import ASSET_MAP
from ..models import MarketSnapshot
from ._styling import _cols, bg_rate, bg_shape, pct, price


def render_tab_relative(snapshot: MarketSnapshot) -> None:
    tabs = st.tabs(["Curve Shape", "Calendar Commodity", "Rate Spread"])

    with tabs[0]:
        _render_curve_shape(snapshot)
    with tabs[1]:
        _render_calendar_commodity(snapshot)
    with tabs[2]:
        _render_rate_spread(snapshot)


# ---- Curve Shape ------------------------------------------------------------

def _render_curve_shape(snapshot: MarketSnapshot) -> None:
    st.subheader("Форма кривой")
    st.caption("Контанго / Бэквордация / Смешанная — по всем активам")

    rows = []
    for asset_code, contracts in snapshot.futures.items():
        mapping = ASSET_MAP.get(asset_code)
        if mapping is None:
            continue
        valid = [c for c in contracts if c.price is not None and c.days_to_expiry > 0]
        if not valid:
            continue
        valid.sort(key=lambda c: c.days_to_expiry)
        front = valid[0]
        back = valid[-1]

        spread = back.price - front.price

        if len(valid) < 2:
            shape = "\u2014"
        else:
            prices = [c.price for c in valid]
            diffs = [prices[i + 1] - prices[i] for i in range(len(prices) - 1)]
            if all(d >= 0 for d in diffs):
                shape = "КОНТАНГО"
            elif all(d <= 0 for d in diffs):
                shape = "БЭКВОРДАЦИЯ"
            else:
                shape = "СМЕШАННАЯ"

        rows.append({
            "Актив": mapping["name"],
            "Код": asset_code,
            "Рынок": mapping.get("market", ""),
            "Контр.": len(valid),
            "Front": f"{front.secid} = {front.price:,.4f}",
            "Back": f"{back.secid} = {back.price:,.4f}",
            "Форма": shape,
            "Спред": spread,
        })

    if not rows:
        st.info("Нет данных")
        return

    market_order = {"currency": 0, "index": 1, "commodity": 2, "stock": 3}
    rows.sort(key=lambda r: (market_order.get(r["Рынок"], 99), r["Актив"]))

    df = pd.DataFrame(rows)
    styler = (
        df.style
        .format({"Спред": price(4)})
        .map(bg_shape, subset=["Форма"])
    )
    st.dataframe(styler, width="stretch", hide_index=True)


# ---- Calendar Commodity -----------------------------------------------------

def _render_calendar_commodity(snapshot: MarketSnapshot) -> None:
    st.subheader("Calendar Commodity")
    st.caption("Календарные спреды товарных фьючерсов (Brent, Gold, Gas и др.)")

    rows = []
    for asset_code, contracts in snapshot.futures.items():
        mapping = ASSET_MAP.get(asset_code)
        if mapping is None or mapping.get("market") != "commodity":
            continue
        valid = [c for c in contracts if c.price is not None and c.days_to_expiry > 0]
        if len(valid) < 2:
            continue
        valid.sort(key=lambda c: c.days_to_expiry)

        for i in range(len(valid) - 1):
            near = valid[i]
            far = valid[i + 1]
            delta_days = far.days_to_expiry - near.days_to_expiry
            if delta_days <= 0 or near.price <= 0:
                continue

            spread = far.price - near.price
            spread_pct = far.price / near.price - 1
            roll_yield = (far.price / near.price - 1) * 365 / delta_days

            rows.append({
                "Актив": mapping["name"],
                "Ближний": near.secid,
                "Дальний": far.secid,
                "Ближн.цена": near.price,
                "Дальн.цена": far.price,
                "Спред": spread,
                "Спред %": spread_pct,
                "Дней": delta_days,
                "Roll Yield": roll_yield,
            })

    if not rows:
        st.info("Нет товарных фьючерсов с 2+ контрактами")
        return

    df = pd.DataFrame(rows)
    styler = (
        df.style
        .format({"Ближн.цена": price(2), "Дальн.цена": price(2),
                 "Спред": price(2), "Спред %": pct(),
                 "Roll Yield": pct()})
        .map(bg_rate, subset=_cols(df, ["Спред %", "Roll Yield"]))
    )
    st.dataframe(styler, width="stretch", hide_index=True)


# ---- Rate Spread ------------------------------------------------------------

def _render_rate_spread(snapshot: MarketSnapshot) -> None:
    st.subheader("Rate Spread")
    st.caption("Implied rate ближнего контракта vs КС ЦБ — по всем активам")

    rows = []
    for asset_code, contracts in snapshot.futures.items():
        mapping = ASSET_MAP.get(asset_code)
        if mapping is None:
            continue

        spot_secid = mapping.get("spot_secid")
        if spot_secid is None:
            continue
        spot_quote = snapshot.spots.get(spot_secid)
        if spot_quote is None or spot_quote.price is None:
            continue
        spot_price = spot_quote.price

        valid = [c for c in contracts if c.price is not None and c.days_to_expiry > 0]
        if not valid:
            continue
        valid.sort(key=lambda c: c.days_to_expiry)
        front = valid[0]

        impl = implied_rate(front.price, spot_price, front.days_to_expiry)
        if impl is None:
            continue
        premium = carry_premium(impl, snapshot.key_rate)

        rows.append({
            "Актив": mapping["name"],
            "Рынок": mapping.get("market", ""),
            "Контракт": front.secid,
            "Дней": front.days_to_expiry,
            "Implied Rate": impl,
            "КС ЦБ": snapshot.key_rate,
            "Спред": premium,
        })

    if not rows:
        st.info("Нет данных")
        return

    market_order = {"currency": 0, "index": 1, "stock": 2}
    rows.sort(key=lambda r: (market_order.get(r["Рынок"], 99), r["Актив"]))

    df = pd.DataFrame(rows)
    rate_cols = _cols(df, ["Implied Rate", "Спред"])
    styler = (
        df.style
        .format({c: pct() for c in rate_cols})
        .format({"КС ЦБ": pct(1, signed=False)})
        .map(bg_rate, subset=rate_cols)
    )
    st.dataframe(styler, width="stretch", hide_index=True)
