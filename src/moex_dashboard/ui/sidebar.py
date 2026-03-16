"""Sidebar: live quotes, cross rates, indices, rates."""

from __future__ import annotations

import streamlit as st

from ..models import MarketSnapshot


def render_sidebar(snapshot: MarketSnapshot) -> None:
    """Render the left sidebar with market data overview."""
    st.header("Котировки")

    if snapshot.stale:
        st.warning("Часть данных устарела или недоступна")

    # --- Currencies ---
    st.subheader("Валюты")
    _spot_metric(snapshot, "USD000UTSTOM", "USDRUB")
    _spot_metric(snapshot, "CNYRUB_TOM", "CNYRUB")
    _spot_metric(snapshot, "EUR_RUB__TOM", "EURRUB")

    # --- Cross rates ---
    usdrub = _spot_price(snapshot, "USD000UTSTOM")
    cnyrub = _spot_price(snapshot, "CNYRUB_TOM")
    eurrub = _spot_price(snapshot, "EUR_RUB__TOM")

    st.subheader("Кроссы")
    if usdrub and cnyrub and cnyrub > 0:
        st.metric("USDCNY", f"{usdrub / cnyrub:.4f}")
    if eurrub and usdrub and usdrub > 0:
        st.metric("EURUSD", f"{eurrub / usdrub:.4f}")

    # --- Indices ---
    st.subheader("Индексы")
    _spot_metric(snapshot, "IMOEX", "IMOEX")
    _spot_metric(snapshot, "RTSI", "RTSI")

    # --- Rates ---
    st.subheader("Ставки")
    st.metric("КС ЦБ", f"{snapshot.key_rate * 100:.1f}%")
    if snapshot.rusfar is not None:
        st.metric("RUSFAR", f"{snapshot.rusfar * 100:.2f}%")
    else:
        st.metric("RUSFAR", "N/A")

    # --- Timestamp ---
    st.caption(f"Обновлено: {snapshot.timestamp:%H:%M:%S}")


def _spot_price(snapshot: MarketSnapshot, secid: str) -> float | None:
    q = snapshot.spots.get(secid)
    return q.price if q else None


def _spot_metric(snapshot: MarketSnapshot, secid: str, label: str) -> None:
    price = _spot_price(snapshot, secid)
    if price is not None:
        st.metric(label, f"{price:,.4f}")
    else:
        st.metric(label, "—")
