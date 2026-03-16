"""Tab: Акции — stock carry curves and implied dividends."""

from __future__ import annotations

import streamlit as st

from ..calc.pipeline import build_curves_table, build_stocks_table
from ..config import ASSET_MAP
from ..models import MarketSnapshot
from ._styling import _cols, bg_rate, pct, price


def render_tab_stocks(snapshot: MarketSnapshot) -> None:
    st.subheader("Акции — Carry кривые")

    df = build_stocks_table(snapshot)
    if df.empty:
        st.info("Нет данных по акциям (возможно, торги ещё не начались)")
        return

    st.download_button("CSV", df.to_csv(index=False), "stocks.csv", "text/csv")

    rate_cols = _cols(df, ["Ближн.rate", "Дальн.rate"])
    div_cols = _cols(df, ["Div %"])

    styler = (
        df.style
        .format({c: pct() for c in rate_cols})
        .format({"Div %": pct(2, signed=False), "Div руб.": price(1),
                 "Спот": price(2), "Ближн.цена": price(2), "Дальн.цена": price(2)})
        .map(bg_rate, subset=rate_cols)
    )
    st.dataframe(styler, width="stretch", hide_index=True)

    # Detail curves per stock
    st.markdown("---")
    stock_codes = [
        code for code, m in ASSET_MAP.items()
        if m.get("market") == "stock" and code in snapshot.futures
    ]
    if stock_codes:
        selected = st.selectbox(
            "Детальная кривая акции",
            stock_codes,
            format_func=lambda c: ASSET_MAP[c]["name"],
        )
        curve_df = build_curves_table(snapshot, selected)
        if not curve_df.empty:
            disp = curve_df.drop(columns=["Тип базы"], errors="ignore").copy()
            disp_rate_cols = _cols(disp, ["Implied Rate", "Премия к КС"])
            styler2 = (
                disp.style
                .format({c: pct() for c in disp_rate_cols})
                .format({"Цена": price(2), "База": price(2)})
                .map(bg_rate, subset=disp_rate_cols)
            )
            st.dataframe(styler2, width="stretch", hide_index=True)
        else:
            st.info("Нет фьючерсных данных для этой акции")
