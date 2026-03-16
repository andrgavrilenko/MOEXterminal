"""Tab: Акции — Carry curves + Dividend calendar."""

from __future__ import annotations

import streamlit as st

from ..calc.pipeline import build_curves_table, build_stocks_table
from ..config import ASSET_MAP
from ..models import MarketSnapshot
from ..services.dividend_service import DividendService
from ._styling import _cols, bg_rate, number, pct, price

_div_svc = DividendService()


def render_tab_stocks(snapshot: MarketSnapshot) -> None:
    sub1, sub2 = st.tabs(["Carry кривые", "Дивиденды"])
    with sub1:
        _render_carry(snapshot)
    with sub2:
        _render_dividends()


# ---------------------------------------------------------------------------
# Carry curves (unchanged)
# ---------------------------------------------------------------------------

def _render_carry(snapshot: MarketSnapshot) -> None:
    st.subheader("Акции — Carry кривые")

    df = build_stocks_table(snapshot)
    if df.empty:
        st.info("Нет данных по акциям (возможно, торги ещё не начались)")
        return

    st.download_button("CSV", df.to_csv(index=False), "stocks.csv", "text/csv")

    rate_cols = _cols(df, ["Ближн.rate", "Дальн.rate"])

    styler = (
        df.style
        .format({c: pct() for c in rate_cols})
        .format({"Div %": pct(2, signed=False), "Div руб.": price(1),
                 "Спот": price(2), "Ближн.цена": price(2), "Дальн.цена": price(2)})
        .map(bg_rate, subset=rate_cols)
    )
    st.dataframe(styler, width="stretch", hide_index=True)

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


# ---------------------------------------------------------------------------
# Dividend calendar
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def _get_div_table(days: int, min_tier: int):
    return _div_svc.get_table(days=days, min_tier=min_tier)


def _render_dividends() -> None:
    st.subheader("Дивидендный календарь")
    st.caption(
        "Предстоящие дивиденды по акциям MOEX. "
        "DSI = Dividend Stability Index (0–1, источник dohod.ru). "
        "Экс-дата ≈ Рек.дата − 2 дня (T+2 расчёты MOEX)."
    )

    col1, col2 = st.columns([2, 1])
    with col1:
        days = st.slider("Горизонт (дней)", min_value=30, max_value=365, value=90, step=30)
    with col2:
        min_tier = st.selectbox("Минимальный тир", options=[0, 1, 2],
                                format_func=lambda v: {0: "Все", 1: "Tier 1", 2: "Tier 2+"}[v])

    df = _get_div_table(days, min_tier)

    if df.empty:
        st.info("Нет предстоящих дивидендов в выбранном горизонте")
        return

    # Summary metrics
    tier1_count = len(df[df["Тир"] == "T1"])
    tier2_count = len(df[df["Тир"] == "T2"])
    confirmed_count = len(df[df["Подтв."] == "✓"])
    avg_yield = df["Дох.%"].mean() * 100

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Всего событий", len(df))
    m2.metric("Tier 1", tier1_count)
    m3.metric("Подтверждено", confirmed_count)
    m4.metric("Средняя дох.", f"{avg_yield:.1f}%")

    st.markdown("---")
    st.download_button("CSV", df.to_csv(index=False), "dividends.csv", "text/csv")

    def _bg_tier(v):
        if v == "T1":
            return "background-color: rgba(0, 180, 0, 0.25)"
        if v == "T2":
            return "background-color: rgba(0, 180, 0, 0.12)"
        return ""

    def _bg_confirmed(v):
        if v == "✓":
            return "background-color: rgba(0, 140, 255, 0.20)"
        return ""

    def _bg_days(v):
        if not isinstance(v, (int, float)):
            return ""
        if v <= 7:
            return "background-color: rgba(220, 40, 40, 0.25)"   # urgent
        if v <= 21:
            return "background-color: rgba(255, 165, 0, 0.20)"   # soon
        return ""

    styler = (
        df.style
        .format({"Дивиденд": number(2), "Дох.%": pct(2, signed=False), "DSI": "{:.2f}"})
        .map(_bg_tier, subset=["Тир"])
        .map(_bg_confirmed, subset=["Подтв."])
        .map(_bg_days, subset=["Дней до экс"])
    )
    st.dataframe(styler, width="stretch", hide_index=True)

    # --- Nearest events detail ---
    nearest = df[df["Дней до экс"].apply(lambda v: isinstance(v, int) and v <= 30)]
    if not nearest.empty:
        st.markdown("---")
        st.markdown("**Ближайшие (≤ 30 дней до экс-даты):**")
        for _, row in nearest.iterrows():
            tier_badge = f"**[{row['Тир']}]**" if row["Тир"] != "—" else ""
            conf_badge = " ✓ подтверждён" if row["Подтв."] == "✓" else ""
            st.markdown(
                f"{tier_badge} **{row['Тикер']}** {row['Название']} — "
                f"дивиденд **{row['Дивиденд']:.2f} руб.** ({row['Дох.%']:.2%}), "
                f"экс-дата {row['Экс-дата']} (через {row['Дней до экс']} дн.){conf_badge}"
            )
