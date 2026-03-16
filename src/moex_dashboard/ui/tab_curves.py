"""Tab: Кривые — futures curves per asset with implied rates."""

from __future__ import annotations

import streamlit as st

from ..calc.pipeline import build_curves_table
from ..config import ASSET_MAP
from ..models import MarketSnapshot
from ._styling import _cols, bg_rate, pct, price


def render_tab_curves(snapshot: MarketSnapshot) -> None:
    st.subheader("Фьючерсные кривые")

    # Build list of available assets (those with futures data)
    available = [
        code for code in ASSET_MAP
        if code in snapshot.futures and len(snapshot.futures[code]) > 0
    ]
    if not available:
        st.info("Нет доступных фьючерсов")
        return

    labels = {code: f"{ASSET_MAP[code]['name']} ({code})" for code in available}
    selected = st.selectbox(
        "Актив",
        available,
        format_func=lambda c: labels[c],
    )

    df = build_curves_table(snapshot, selected)
    if df.empty:
        mapping = ASSET_MAP.get(selected, {})
        if mapping.get("market") == "commodity":
            st.info("Нужно минимум 2 контракта для товарной кривой (base = front contract)")
        else:
            st.info("Нет данных для этого актива")
        return

    # Show base type info
    if "Тип базы" in df.columns and not df.empty:
        base_type = df["Тип базы"].iloc[0]
        if base_type != "Spot":
            st.caption(f"База: {base_type} (для товаров без спота — ближний контракт)")

    # Display table
    display = df.drop(columns=["Тип базы"], errors="ignore").copy()
    rate_cols = _cols(display, ["Implied Rate", "Премия к КС"])

    styler = (
        display.style
        .format({c: pct() for c in rate_cols})
        .format({"Цена": price(4), "База": price(4)})
        .map(bg_rate, subset=rate_cols)
    )
    st.dataframe(styler, width="stretch", hide_index=True)

    # Line chart: implied rate vs days to expiry
    if len(df) > 1:
        chart_df = df[["Дней", "Implied Rate"]].copy()
        chart_df["Implied Rate (%)"] = chart_df["Implied Rate"] * 100
        chart_df = chart_df.set_index("Дней")
        st.line_chart(chart_df["Implied Rate (%)"])
